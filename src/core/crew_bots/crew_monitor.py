import asyncio
import multiprocessing
from typing import Optional, Dict, Set, List
import threading
from datetime import datetime
import os
from uuid import UUID

from src.crewai_ext.tools.opera_api.staff_api_tool import StaffTool
from src.crewai_ext.tools.opera_api.staff_invitation_api_tool import StaffInvitationTool
from src.opera_service.api.models import StaffInvitationForCreation
from src.opera_service.signalr_client.opera_signalr_client import OperaSignalRClient, OperaCreatedArgs
from src.core.logger_config import get_logger_with_trace_id
from src.crewai_ext.tools.opera_api.bot_api_tool import BotTool
from src.core.parser.api_response_parser import ApiResponseParser

from src.core.crew_process_starters import start_crew_manager_process, start_crew_runner_process

# 从环境变量读取Bot名称过滤条件，默认为"CM"
MANAGER_ROLE_FILTER = os.environ.get("MANAGER_ROLE_FILTER", "CrewManager")
RUNNER_ROLE_FILTER = os.environ.get("RUNNER_ROLE_FILTER", "CrewRunner")  # 新增Runner角色过滤条件
MONITOR_ROLE_FILTER = os.environ.get("MONITOR_ROLE_FILTER", "CrewMonitor")  # 新增Monitor角色过滤条件


class CrewMonitor:
    """监控器类，用于监听新的Opera和Bot创建事件，并动态启动相应的进程"""

    def __init__(self):
        self.log = get_logger_with_trace_id()
        self.signalr_client = OperaSignalRClient()
        self.bot_tool = BotTool()
        self.staff_tool = StaffTool()
        self.staff_invitation_tool = StaffInvitationTool()
        self.parser = ApiResponseParser()
        self.processes: Dict[str, multiprocessing.Process] = {}  # 存储所有进程，key为bot_id
        self.managed_bots: Set[str] = set()  # 存储已经启动了进程的bot id
        self.lock = threading.Lock()  # 用于保护共享资源
        self.restart_history: Dict[str, float] = {}  # 记录Bot重启历史，key为bot_id，value为重启时间戳
        self.restart_cooldown = 60  # 重启冷却时间（秒），避免频繁重启

        # 添加Bot缓存和缓存时间
        self.bot_cache: List[Dict] = []  # 缓存的Bot列表
        self.bot_cache_time: float = 0  # 缓存的更新时间戳
        self.bot_cache_ttl = 300  # 缓存有效期（秒）

        self.managed_manager_bots: Set[str] = set()  # 存储已经启动了进程的Manager bot id
        self.managed_runner_bots: Set[str] = set()  # 存储已经启动了进程的Runner bot id

        self.bot_id: Optional[str] = None

    def _is_crew_manager_bot(self, bot: Dict) -> bool:
        """检查Bot是否是CrewManager角色

        Args:
            bot: Bot数据字典

        Returns:
            是否是CrewManager Bot
        """
        roles = bot.get("defaultRoles")
        return (
            # 处理defaultRoles可能是字符串的情况
            roles == MANAGER_ROLE_FILTER
            or
            # 处理defaultRoles可能是列表的情况
            (isinstance(roles, list) and MANAGER_ROLE_FILTER in roles)
        )

    def _is_crew_runner_bot(self, bot: Dict) -> bool:
        """检查Bot是否是CrewRunner角色

        Args:
            bot: Bot数据字典

        Returns:
            是否是CrewRunner Bot
        """
        roles = bot.get("defaultRoles")
        return (
            # 处理defaultRoles可能是字符串的情况
            roles == RUNNER_ROLE_FILTER
            or
            # 处理defaultRoles可能是列表的情况
            (isinstance(roles, list) and RUNNER_ROLE_FILTER in roles)
        )

    def _is_crew_monitor_bot(self, bot: Dict) -> bool:
        """检查Bot是否是CrewMonitor角色

        Args:
            bot: Bot数据字典

        Returns:
            是否是CrewMonitor Bot
        """
        roles = bot.get("defaultRoles")
        return (
            # 处理defaultRoles可能是字符串的情况
            roles == MONITOR_ROLE_FILTER
            or
            # 处理defaultRoles可能是列表的情况
            (isinstance(roles, list) and MONITOR_ROLE_FILTER in roles)
        )

    async def start(self):
        """启动监控器"""
        self.log.info("启动CrewMonitor...")

        # 设置SignalR客户端回调
        self.signalr_client.set_callback("on_opera_created", self._on_opera_created)

        # 连接SignalR服务
        await self.signalr_client.connect_with_retry()

        # 初始化现有的bot
        await self._init_existing_bots()

        self.log.info("CrewMonitor已启动")

    async def stop(self):
        """停止监控器"""
        self.log.info("正在停止CrewMonitor...")

        try:
            # 断开SignalR连接
            if self.signalr_client._connected:
                self.log.info("正在断开SignalR连接...")
                try:
                    await self.signalr_client.disconnect()
                    self.log.info("SignalR连接已断开")
                except Exception as e:
                    self.log.error(f"断开SignalR连接时出错: {str(e)}")
                    # 如果断开失败，尝试直接重置状态
                    self.signalr_client._connected = False
                    self.signalr_client.client = None
                    self.log.info("已强制重置SignalR客户端状态")

            # 停止所有进程
            with self.lock:
                process_count = len(self.processes)
                if process_count > 0:
                    self.log.info(f"正在停止{process_count}个Bot进程...")

                    for bot_id, process in list(self.processes.items()):
                        try:
                            if process.is_alive():
                                self.log.info(f"正在停止Bot {bot_id}的进程...")
                                process.terminate()
                                # 给进程一些时间来正常终止
                                process.join(timeout=2.0)

                                # 如果仍然活跃，强制结束
                                if process.is_alive():
                                    self.log.warning("进程未在超时时间内终止，强制结束")
                                    import signal

                                    try:
                                        os.kill(process.pid, signal.SIGKILL)
                                    except Exception as e:
                                        self.log.error(f"强制终止进程时出错: {str(e)}")
                            else:
                                self.log.info(f"Bot {bot_id}的进程已不再活跃")
                        except Exception as e:
                            self.log.error(f"停止Bot {bot_id}的进程时出错: {str(e)}")
                else:
                    self.log.info("没有需要停止的进程")

                # 清空进程列表和管理的bot集合
                self.processes.clear()
                self.managed_bots.clear()
                self.managed_manager_bots.clear()
                self.managed_runner_bots.clear()
                self.log.info("已清除所有进程记录和Bot管理列表")
        except Exception as e:
            self.log.error(f"停止CrewMonitor时出错: {str(e)}")
        finally:
            self.log.info("CrewMonitor已停止")

    async def _init_existing_bots(self):
        """初始化现有的Bots"""
        self.log.info("正在初始化现有Bots...")

        # 获取所有Bot
        result = self.bot_tool.run(action="get_all")

        try:
            status_code, bots_data = self.parser.parse_response(result)

            if status_code == 200:
                # 更新Bot缓存
                self.bot_cache = bots_data
                self.bot_cache_time = asyncio.get_event_loop().time()

                # 查找CrewMonitor角色的bot并设置为自己的bot id
                crew_monitor_bots = [bot for bot in bots_data if self._is_crew_monitor_bot(bot)]
                if crew_monitor_bots:
                    self.bot_id = crew_monitor_bots[0]["id"]
                    self.log.info(f"找到CrewMonitor Bot，ID: {self.bot_id}，名称: {crew_monitor_bots[0]['name']}")
                    # 设置SignalR客户端的bot id
                    if self.signalr_client._connected:
                        # 如果已连接，则创建异步任务设置bot id
                        asyncio.create_task(self.signalr_client.set_bot_id(UUID(self.bot_id)))
                        self.log.info(f"已发送Bot ID: {self.bot_id}到SignalR服务器")
                    else:
                        # 如果未连接，则只设置实例变量
                        self.signalr_client.bot_id = UUID(self.bot_id)
                        self.log.info(f"已设置Bot ID: {self.bot_id}，连接后将自动发送")
                else:
                    self.log.warning("未找到CrewMonitor角色的Bot，SignalR客户端将使用默认设置")

                # 过滤符合条件的Bot，包括已管理但可能已停止的bot
                crew_manager_bots = [bot for bot in bots_data if self._is_crew_manager_bot(bot) and not bot["isActive"]]

                if crew_manager_bots:
                    self.log.info(f"发现{len(crew_manager_bots)}个符合条件的Bot")

                    # 为每个符合条件的Bot启动或重启CrewManager进程
                    for bot in crew_manager_bots:
                        await self._start_bot_manager(bot["id"], bot["name"])
            else:
                self.log.error(f"获取Bot列表失败，状态码: {status_code}")
        except Exception as e:
            self.log.error(f"初始化现有Bots时出错: {str(e)}")

    async def _get_crew_manager_bots(self, force_refresh: bool = False) -> List[Dict]:
        """获取符合条件的CrewManager Bot列表

        Args:
            force_refresh: 是否强制刷新缓存

        Returns:
            符合条件的Bot列表
        """
        # 确保Bot缓存是最新的
        await self._update_bot_cache(force_refresh)

        # 从缓存中筛选Manager Bot
        return [bot for bot in self.bot_cache if self._is_crew_manager_bot(bot)]

    async def _get_crew_runner_bots(self, force_refresh: bool = False) -> List[Dict]:
        """获取符合条件的CrewRunner Bot列表

        Args:
            force_refresh: 是否强制刷新缓存

        Returns:
            符合条件的Bot列表
        """
        # 确保Bot缓存是最新的
        await self._update_bot_cache(force_refresh)

        # 从缓存中筛选Runner Bot
        return [bot for bot in self.bot_cache if self._is_crew_runner_bot(bot)]

    async def _update_bot_cache(self, force_refresh: bool = False) -> None:
        """更新Bot缓存

        Args:
            force_refresh: 是否强制刷新缓存
        """
        current_time = asyncio.get_event_loop().time()

        # 如果缓存有效且不强制刷新，直接返回
        if not force_refresh and self.bot_cache and current_time - self.bot_cache_time < self.bot_cache_ttl:
            return

        # 否则重新获取Bot列表
        try:
            result = self.bot_tool._run(action="get_all")
            status_code, bots_data = self.parser.parse_response(result)

            if status_code == 200:
                # 更新缓存和时间戳
                self.bot_cache = bots_data
                self.bot_cache_time = current_time
            else:
                self.log.error(f"获取Bot列表失败，状态码: {status_code}")
                # 如果请求失败但有缓存，保留现有缓存
                if not self.bot_cache:
                    self.log.error("没有可用的Bot缓存备用")
        except Exception as e:
            self.log.error(f"更新Bot缓存时出错: {str(e)}")
            # 如果发生异常但没有缓存，记录错误
            if not self.bot_cache:
                self.log.error("更新Bot缓存失败且没有可用的缓存备用")

    async def _on_opera_created(self, opera_args: OperaCreatedArgs):
        """处理新建Opera事件"""
        self.log.info(f"CrewMonitor收到新建Opera事件: {opera_args.name}, Opera ID: {opera_args.opera_id}")

        try:
            # 获取Opera的ID
            opera_id_str = str(opera_args.opera_id)

            # 检查该Opera是否已有符合条件的crew_manager_bots作为staff
            staff_result = self.staff_tool.run(action="get_all", opera_id=opera_id_str)
            staff_status, staff_data = self.parser.parse_response(staff_result)

            if staff_status != 200:
                self.log.error(f"获取Opera {opera_args.name} 的Staff信息失败，状态码: {staff_status}")
                return

            # 检查是否有具有CrewManager角色的staff
            crew_manager_staffs = []
            if staff_data and isinstance(staff_data, list):  # 确保staff_data是一个列表
                crew_manager_staffs = [
                    staff for staff in staff_data if staff.get("botId") and "CrewManager" in (staff.get("roles") or [])
                ]

            if crew_manager_staffs:
                self.log.info(f"Opera {opera_args.name} 已有具有CrewManager角色的Bot作为staff")

                # 检查这些Bot是否已经在管理列表中
                with self.lock:
                    for staff in crew_manager_staffs:
                        bot_id = staff.get("botId")
                        if bot_id and bot_id not in self.managed_bots:
                            self.log.info(f"为已有的Bot {staff.get('botName')} (ID: {bot_id})启动进程")
                            await self._start_bot_manager(bot_id, staff.get("botName"))
                return  # 有具有CrewManager角色的Bot作为staff，直接返回

            # 如果没有符合条件的CrewManager staff，则查找现有的CrewManager Bot并注册为staff
            self.log.info(f"为Opera {opera_args.name} (ID: {opera_args.opera_id})注册现有的CrewManager Bot...")

            # 获取所有符合条件的Bot（使用缓存机制）
            crew_manager_bots = await self._get_crew_manager_bots()

            if not crew_manager_bots:
                self.log.error(f"未找到符合条件的CrewManager Bot，无法为新Opera {opera_args.name}注册staff")
                return

            # 选择第一个符合条件的Bot作为staff
            selected_bot = crew_manager_bots[0]
            bot_id = selected_bot["id"]
            bot_name = selected_bot["name"]

            # 注册Bot为新Opera的staff
            invitation_result = self.staff_invitation_tool.run(
                action="create",
                opera_id=opera_id_str,
                data=StaffInvitationForCreation(
                    bot_id=bot_id,
                    tags="",
                    roles="CrewManager",
                    permissions="manager",
                    parameter="{}",
                ),
            )
            invitation_status, invitation_data = self.parser.parse_response(invitation_result)

            if invitation_status == 201:
                self.log.info(f"成功向Bot {bot_name} (ID: {bot_id})发送Opera {opera_args.name}的staff邀请")

                # 确保不重复启动进程
                with self.lock:
                    if bot_id not in self.managed_bots:
                        await self._start_bot_manager(bot_id, bot_name)
            else:
                self.log.error(f"发送staff邀请失败，状态码: {invitation_status}")

        except Exception as e:
            self.log.error(f"处理Opera创建事件时出错: {str(e)}")

    async def _check_bots(self):
        """定期检查新的Bot和已管理但可能非活跃的Bot"""
        # 获取当前时间
        current_time = asyncio.get_event_loop().time()

        # 获取所有Bot (使用缓存机制)
        try:
            # 强制刷新缓存，确保数据最新
            crew_manager_bots = await self._get_crew_manager_bots(force_refresh=True)
            crew_runner_bots = await self._get_crew_runner_bots()  # 获取Runner Bot
            all_bots = self.bot_cache  # 使用完整的缓存列表

            if all_bots:
                # 1. 检查新的符合条件的Bot (Manager)
                new_crew_manager_bots = [
                    bot for bot in crew_manager_bots if not bot["isActive"] and bot["id"] not in self.managed_bots
                ]

                if new_crew_manager_bots:
                    self.log.info(f"发现{len(new_crew_manager_bots)}个新的符合条件的CrewManager Bot")

                    # 为每个新的符合条件的Bot启动CrewManager进程
                    for bot in new_crew_manager_bots:
                        await self._start_bot_manager(bot["id"], bot["name"])

                # 1.1 检查新的符合条件的Bot (Runner)
                new_crew_runner_bots = [
                    bot for bot in crew_runner_bots if not bot["isActive"] and bot["id"] not in self.managed_bots
                ]

                if new_crew_runner_bots:
                    self.log.info(f"发现{len(new_crew_runner_bots)}个新的符合条件的CrewRunner Bot")

                    # 为每个新的符合条件的Bot启动CrewRunner进程
                    for bot in new_crew_runner_bots:
                        # 从标签中获取父Bot ID (如果有)
                        default_tags = self.parser.parse_default_tags(bot)
                        parent_bot_id = default_tags.get("ParentBotId")

                        await self._start_bot_runner(bot["id"], bot["name"], parent_bot_id)

                # 2. 检查已管理但可能已经在Opera中变为非活跃的Bot (Manager和Runner)
                with self.lock:
                    managed_bot_ids = self.managed_bots.copy()

                # 找出已管理但在Opera中显示为非活跃的Bot，同时考虑冷却期
                inactive_managed_bots = []
                for bot in all_bots:
                    bot_id = bot["id"]

                    # 条件1：已在管理列表中
                    # 条件2：在Opera中显示为非活跃
                    # 条件3：不在冷却期内或从未重启过
                    if (
                        bot_id in managed_bot_ids
                        and not bot["isActive"]
                        and (
                            bot_id not in self.restart_history
                            or current_time - self.restart_history[bot_id] >= self.restart_cooldown
                        )
                    ):
                        inactive_managed_bots.append(bot)

                if inactive_managed_bots:
                    self.log.info(f"发现{len(inactive_managed_bots)}个需要重启的非活跃Bot")

                    # 重新启动这些Bot的进程
                    for bot in inactive_managed_bots:
                        bot_id = bot["id"]
                        self.log.info(f"Bot {bot['name']}(ID: {bot_id})在Opera中显示为非活跃，将重新启动...")

                        with self.lock:
                            # 从管理列表中移除，以便重新启动它
                            if bot_id in self.managed_bots:
                                self.managed_bots.remove(bot_id)
                            if bot_id in self.managed_manager_bots:
                                self.managed_manager_bots.remove(bot_id)
                            if bot_id in self.managed_runner_bots:
                                self.managed_runner_bots.remove(bot_id)

                            # 如果存在相关进程，终止它
                            if bot_id in self.processes:
                                process = self.processes[bot_id]
                                if process.is_alive():
                                    self.log.info(f"终止Bot {bot_id}的现有进程")
                                    process.terminate()
                                    process.join()
                                del self.processes[bot_id]

                        # 记录重启时间
                        self.restart_history[bot_id] = current_time

                        # 根据Bot角色重新启动对应进程
                        if self._is_crew_manager_bot(bot):
                            await self._start_bot_manager(bot_id, bot["name"])
                        elif self._is_crew_runner_bot(bot):
                            # 从标签中获取父Bot ID (如果有)
                            default_tags = self.parser.parse_default_tags(bot)
                            parent_bot_id = default_tags.get("ParentBotId")

                            await self._start_bot_runner(bot_id, bot["name"], parent_bot_id)

                # 3. 检查已管理但可能已被删除的Bot
                existing_bot_ids = {bot["id"] for bot in all_bots}
                with self.lock:
                    deleted_bot_ids = [bot_id for bot_id in self.managed_bots if bot_id not in existing_bot_ids]

                if deleted_bot_ids:
                    self.log.info(f"发现{len(deleted_bot_ids)}个已被删除的Bot，将停止其对应进程")

                    for bot_id in deleted_bot_ids:
                        self.log.info(f"Bot ID: {bot_id}已不存在，停止其对应进程并从管理列表中移除")

                        with self.lock:
                            # 从管理列表中移除
                            if bot_id in self.managed_bots:
                                self.managed_bots.remove(bot_id)
                            if bot_id in self.managed_manager_bots:
                                self.managed_manager_bots.remove(bot_id)
                            if bot_id in self.managed_runner_bots:
                                self.managed_runner_bots.remove(bot_id)

                            # 终止对应进程
                            if bot_id in self.processes:
                                process = self.processes[bot_id]
                                if process.is_alive():
                                    self.log.info(f"终止已删除Bot {bot_id}的进程")
                                    process.terminate()
                                    process.join()
                                del self.processes[bot_id]

                            # 清理重启历史
                            if bot_id in self.restart_history:
                                del self.restart_history[bot_id]
            else:
                self.log.error("获取Bot列表失败或没有符合条件的Bot")
        except Exception as e:
            self.log.error(f"检查Bot时出错: {str(e)}")

    async def _start_bot_manager(self, bot_id: str, bot_name: str):
        """为指定Bot启动CrewManager进程"""
        self.log.info(f"正在为Bot {bot_name}(ID: {bot_id})启动CrewManager进程...")

        with self.lock:
            # 检查是否已经在管理这个Bot
            if bot_id in self.managed_bots:
                self.log.info(f"Bot {bot_id}已经在管理中，避免重复启动")
                return

            # 检查进程是否已经存在但未记录
            for process_bot_id, process in self.processes.items():
                if process_bot_id == bot_id:
                    if process.is_alive():
                        self.log.info(f"Bot {bot_id}的进程已存在且活跃，仅更新记录")
                        self.managed_bots.add(bot_id)
                        self.managed_manager_bots.add(bot_id)  # 更新Manager Bot集合
                        return
                    else:
                        self.log.info(f"Bot {bot_id}的进程已存在但已停止，将重新启动")
                        process.terminate()
                        process.join()
                        del self.processes[bot_id]
                        break

            # 启动新进程
            process = multiprocessing.Process(target=start_crew_manager_process, args=(bot_id,))
            process.start()

            # 记录进程和Bot
            self.processes[bot_id] = process
            self.managed_bots.add(bot_id)
            self.managed_manager_bots.add(bot_id)  # 更新Manager Bot集合

            # 记录重启时间
            self.restart_history[bot_id] = asyncio.get_event_loop().time()

            self.log.info(f"已为Bot {bot_id}启动CrewManager进程")

    async def _start_bot_runner(self, bot_id: str, bot_name: str, parent_bot_id: Optional[str] = None):
        """为指定Bot启动CrewRunner进程

        Args:
            bot_id: Runner Bot ID
            bot_name: Runner Bot名称
            parent_bot_id: 父Bot ID，如果不提供则为独立Runner
        """
        self.log.info(f"正在为Bot {bot_name}(ID: {bot_id})启动CrewRunner进程...")

        with self.lock:
            # 检查是否已经在管理这个Bot
            if bot_id in self.managed_bots:
                self.log.info(f"Bot {bot_id}已经在管理中，避免重复启动")
                return

            # 检查进程是否已经存在但未记录
            for process_bot_id, process in self.processes.items():
                if process_bot_id == bot_id:
                    if process.is_alive():
                        self.log.info(f"Bot {bot_id}的进程已存在且活跃，仅更新记录")
                        self.managed_bots.add(bot_id)
                        self.managed_runner_bots.add(bot_id)  # 更新Runner Bot集合
                        return
                    else:
                        self.log.info(f"Bot {bot_id}的进程已存在但已停止，将重新启动")
                        process.terminate()
                        process.join()
                        del self.processes[bot_id]
                        break

            # 确定父Bot ID
            parent_id = parent_bot_id if parent_bot_id else "00000000-0000-0000-0000-000000000000"

            # 启动新进程
            process = multiprocessing.Process(target=start_crew_runner_process, args=(bot_id, parent_id))
            process.start()

            # 记录进程和Bot
            self.processes[bot_id] = process
            self.managed_bots.add(bot_id)
            self.managed_runner_bots.add(bot_id)  # 更新Runner Bot集合

            # 记录重启时间
            self.restart_history[bot_id] = asyncio.get_event_loop().time()

            self.log.info(f"已为Bot {bot_id}启动CrewRunner进程，父Bot ID: {parent_id}")

    async def _check_monitor_status(self):
        """检查Monitor Bot状态并在必要时重连SignalR

        这是一个轻量级检查，只关注Monitor自身的Bot状态和SignalR连接状态。
        """
        # 获取当前时间
        current_time = asyncio.get_event_loop().time()
        # 转换为可读的时间格式
        readable_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            # 检查缓存是否为空
            if not self.bot_cache:
                await self._update_bot_cache(force_refresh=True)  # 强制刷新缓存
                if not self.bot_cache:  # 如果刷新后仍为空
                    self.log.error("无法获取Bot缓存，跳过本次监控检查")
                    return  # 如果缓存为空，直接返回，不进行后续检查

            # 检查缓存是否过期
            if (current_time - self.bot_cache_time) >= self.bot_cache_ttl:
                self.log.info(f"Bot缓存已过期（当前缓存时间: {self.bot_cache_time}，TTL: {self.bot_cache_ttl}秒），强制刷新")
                await self._update_bot_cache(force_refresh=True)  # 缓存过期，强制刷新

            # 使用最新的缓存
            all_bots = self.bot_cache

            if all_bots:
                # 1. 如果没有设置Monitor Bot ID，尝试查找合适的CrewMonitor Bot
                if self.bot_id is None:
                    crew_monitor_bots = [bot for bot in all_bots if self._is_crew_monitor_bot(bot)]
                    if crew_monitor_bots:
                        self.bot_id = crew_monitor_bots[0]["id"]
                        self.log.info("找到CrewMonitor Bot，ID: {self.bot_id}，名称: {crew_monitor_bots[0]['name']}")

                        # 设置SignalR客户端的bot id
                        self.signalr_client.bot_id = UUID(self.bot_id)

                        # 无论SignalR客户端是否已连接，都发送bot id
                        asyncio.create_task(self.signalr_client.set_bot_id(UUID(self.bot_id)))
                        self.log.info(f"已发送Bot ID: {self.bot_id}到SignalR服务器")
                    else:
                        self.log.warning("未找到CrewMonitor角色的Bot，继续使用无身份连接")

                # 2. 如果已设置Monitor Bot ID，检查状态
                if self.bot_id is not None:
                    # 查找Monitor使用的Bot
                    monitor_bot = next((bot for bot in all_bots if bot["id"] == self.bot_id), None)

                    # 检查是否需要重连SignalR
                    need_reconnect = False
                    reconnect_reason = ""

                    # 只根据isActive状态决定是否重连
                    if monitor_bot and not monitor_bot["isActive"]:
                        need_reconnect = True
                        reconnect_reason = f"Monitor Bot {monitor_bot['name']} (ID: {self.bot_id})显示为非活跃状态"
                        self.log.debug("检测到Monitor Bot非活跃状态")
                    # 情况2: Bot不存在，需要重置bot_id并寻找新的Bot
                    elif not monitor_bot:
                        self.bot_id = None  # 重置标志，下次检查时会重新查找
                        self.log.warning("原Monitor Bot不存在，将在下次检查时寻找新的Bot")
                    elif monitor_bot and monitor_bot["isActive"]:
                        # Bot活跃状态正常，不需要重连
                        self.log.trace(f"Monitor Bot状态正常：{monitor_bot['name']} (ID: {self.bot_id})")

                    # 如果需要重连，并且不在冷却期内
                    if need_reconnect:
                        last_reconnect_time = self.restart_history.get("signalr_client", 0)
                        time_since_last_reconnect = current_time - last_reconnect_time

                        if time_since_last_reconnect >= self.restart_cooldown:
                            self.log.warning(f"{reconnect_reason}，重启SignalR客户端...")

                            # 记录重连时间
                            self.restart_history["signalr_client"] = current_time

                            # 重新连接SignalR客户端
                            try:
                                # 先断开现有连接
                                await self.signalr_client.disconnect()
                                self.log.info("已断开SignalR客户端连接")

                                # 等待足够的时间确保连接完全断开
                                await asyncio.sleep(3)

                                # 检查连接是否真的断开
                                if hasattr(self.signalr_client, "is_disconnected") and not self.signalr_client.is_disconnected():
                                    self.log.warning("连接未完全断开，等待更长时间...")
                                    await asyncio.sleep(5)  # 再等待5秒

                                # 重新连接
                                self.log.info("开始重新连接SignalR客户端...")
                                await self.signalr_client.connect_with_retry(max_retries=3, retry_delay=5)
                                self.log.info("SignalR客户端已重新连接")

                                # 等待连接稳定
                                await asyncio.sleep(2)

                                # 重新设置回调
                                self.signalr_client.set_callback("on_opera_created", self._on_opera_created)
                                self.log.info("已重新设置SignalR客户端回调")

                                # 等待连接进一步稳定
                                await asyncio.sleep(3)

                                # 重新设置Bot ID，但确保连接已就绪并添加重试机制
                                if monitor_bot:
                                    self.signalr_client.bot_id = UUID(self.bot_id)

                                    # 检查连接是否就绪
                                    if self.signalr_client._connected and self.signalr_client.client:
                                        try:
                                            # 使用等待而不是创建任务，以便捕获异常
                                            await self.signalr_client.set_bot_id(UUID(self.bot_id))
                                            self.log.info("已成功重新设置Bot ID")
                                        except Exception as e:
                                            self.log.error(f"设置Bot ID时出错: {str(e)}")
                                            # 不抛出异常，让监控器继续运行
                                    else:
                                        self.log.warning("连接未就绪，将在下次检查时尝试设置Bot ID")
                            except RuntimeError as e:
                                # 特别处理"Cannot connect while not disconnected"错误
                                if "Cannot connect while not disconnected" in str(e):
                                    self.log.error(f"连接状态错误: {str(e)}，尝试强制重置客户端...")
                                    # 强制重置SignalR客户端
                                    try:
                                        # 创建新的客户端实例
                                        old_client = self.signalr_client
                                        self.signalr_client = OperaSignalRClient(url=old_client.url)

                                        # 复制必要的状态
                                        self.signalr_client.bot_id = old_client.bot_id
                                        self.signalr_client.snitch_mode = old_client.snitch_mode

                                        # 设置回调
                                        self.signalr_client.set_callback("on_opera_created", self._on_opera_created)

                                        # 尝试连接
                                        await asyncio.sleep(1)  # 短暂等待确保状态稳定
                                        await self.signalr_client.connect_with_retry()
                                        self.log.info("已成功重置并重连SignalR客户端")

                                        # 如果有Bot ID，设置它
                                        if self.bot_id:
                                            await asyncio.sleep(2)  # 等待连接稳定
                                            if self.signalr_client._connected:
                                                await self.signalr_client.set_bot_id(UUID(self.bot_id))
                                                self.log.info("已在重置后设置Bot ID")
                                    except Exception as inner_e:
                                        self.log.error(f"重置SignalR客户端时出错: {str(inner_e)}")
                                else:
                                    self.log.error(f"重新连接SignalR客户端时出错: {str(e)}")
                            except Exception as e:
                                self.log.error(f"重新连接SignalR客户端时出错: {str(e)}")
                        else:
                            self.log.debug(
                                f"需要重连但在冷却期内，距离上次重连: {time_since_last_reconnect:.0f}秒，冷却期: {self.restart_cooldown}秒"
                            )

        except Exception as e:
            self.log.error(f"检查Monitor状态时出错: {str(e)}")

    async def _periodic_check(self, monitor_interval: int = 60, bot_interval: int = 300):
        """定期检查Bot状态

        Args:
            monitor_interval: Monitor状态检查间隔（秒）
            bot_interval: 常规Bot检查间隔（秒）
        """
        await asyncio.sleep(bot_interval)
        last_bot_check_time = 0
        while True:
            current_time = asyncio.get_event_loop().time()

            # 检查是否需要进行完整的Bot检查
            if current_time - last_bot_check_time >= bot_interval:
                await self._check_bots()
                last_bot_check_time = current_time

            # 每次循环都检查Monitor状态
            await self._check_monitor_status()

            # 等待下一次Monitor检查
            await asyncio.sleep(monitor_interval)
