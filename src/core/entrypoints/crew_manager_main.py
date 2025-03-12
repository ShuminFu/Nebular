import asyncio
import multiprocessing
import os
from uuid import UUID
from src.core.logger_config import get_logger, get_logger_with_trace_id, setup_logger
from src.crewai_ext.tools.opera_api.bot_api_tool import BotTool
from src.crewai_ext.tools.opera_api.staff_api_tool import StaffTool
from src.crewai_ext.tools.opera_api.staff_invitation_api_tool import StaffInvitationTool
from src.opera_service.api.models import StaffInvitationForCreation
from src.core.crew_process import CrewManager, CrewRunner, CrewProcessInfo
from src.core.parser.api_response_parser import ApiResponseParser
from src.core.bot_api_helper import (
    fetch_bot_data,
    fetch_staff_data,
    create_child_bot,
    update_parent_bot_tags,
    get_child_bot_opera_ids,
    get_child_bot_staff_info,
)
from src.opera_service.signalr_client.opera_signalr_client import OperaSignalRClient, OperaCreatedArgs

from typing import Optional, Dict, Set, List
import backoff
import threading

# 从环境变量读取Bot名称过滤条件，默认为"CM"
MANAGER_ROLE_FILTER = os.environ.get("MANAGER_ROLE_FILTER", "CrewManager")
RUNNER_ROLE_FILTER = os.environ.get("RUNNER_ROLE_FILTER", "CrewRunner")  # 新增Runner角色过滤条件



# 重试装饰器


@backoff.on_exception(backoff.expo,
                      (asyncio.TimeoutError, ConnectionError),
                      max_tries=3,
                      max_time=300)
async def run_crew_manager(bot_id: str):
    """为单个Bot运行CrewManager"""
    # 为每个manager实例创建新的trace_id
    log = get_logger_with_trace_id()
    manager = CrewManager()
    manager.bot_id = UUID(bot_id)
    bot_tool = BotTool()
    parser = ApiResponseParser()

    try:
        # 1. 获取Bot信息和关联的Opera
        bot_data = await fetch_bot_data(bot_tool, bot_id, log)
        managed_operas = await fetch_staff_data(bot_tool, bot_id, log)

        # 2. 获取现有ChildBots及其管理的Opera
        default_tags = parser.parse_default_tags(bot_data)
        existing_child_bots = parser.get_child_bots(default_tags) or []
        log.info(f"现有ChildBots: {existing_child_bots}")

        # 获取ChildBots管理的Opera
        childbot_related_opera_ids = set()
        for child_bot_id in existing_child_bots:
            opera_ids = await get_child_bot_opera_ids(bot_tool, child_bot_id, log)
            childbot_related_opera_ids.update(opera_ids)

        # 3. 为未覆盖的Opera创建ChildBot
        for opera in managed_operas:
            if str(opera["id"]) not in childbot_related_opera_ids:
                new_bot_ids = await create_child_bot(bot_tool, opera, bot_id, log)
                if new_bot_ids:
                    existing_child_bots.extend(new_bot_ids)
                    await update_parent_bot_tags(bot_tool, bot_id, existing_child_bots, log, existing_bot_data=bot_data)

        # 4. 启动未激活的ChildBots
        for child_bot_id in existing_child_bots:
            try:
                child_bot_data = await fetch_bot_data(bot_tool, child_bot_id, log)

                if not child_bot_data.get("isActive", True):
                    # 获取子Bot的配置信息
                    child_tags = parser.parse_default_tags(child_bot_data)
                    crew_config = child_tags.get("CrewConfig", {})
                    related_operas = child_tags.get("RelatedOperas", [])

                    # 获取子Bot在各个Opera中的staff_id和roles
                    staff_info = await get_child_bot_staff_info(bot_tool, child_bot_id, log)
                    staff_ids = {opera_id: info["staff_ids"] for opera_id, info in staff_info.items()}
                    roles = {opera_id: info["roles"] for opera_id, info in staff_info.items()}

                    # 创建进程并记录信息
                    process = multiprocessing.Process(target=start_crew_runner_process, args=(child_bot_id, bot_id))
                    process.start()
                    log.info(f"已为子Bot {child_bot_id} 启动CrewRunner进程，父Bot ID: {bot_id}")
                    # 创建并存储进程信息
                    process_info = CrewProcessInfo(
                        process=process,
                        bot_id=UUID(child_bot_id),
                        crew_config=crew_config,
                        opera_ids=[UUID(opera_id) for opera_id in related_operas],
                        roles=roles,
                        staff_ids=staff_ids,
                    )
                    manager.crew_processes[UUID(child_bot_id)] = process_info
            except Exception as e:
                log.error(f"处理子Bot {child_bot_id} 时出错: {str(e)}")
                continue

        # 运行CrewManager
        await manager.run()

    except asyncio.TimeoutError:
        log.error(f"Bot {bot_id} 等待连接超时，将进行重试")
        raise
    except KeyboardInterrupt:
        await manager.stop()
        log.info(f"CrewManager已停止，Bot ID: {bot_id}")
    except Exception as e:
        log.error(f"CrewManager运行出错，Bot ID: {bot_id}, 错误: {str(e)}")
        raise


@backoff.on_exception(backoff.expo,
                      (asyncio.TimeoutError, ConnectionError),
                      max_tries=3,
                      max_time=300)
async def run_crew_runner(runner: CrewRunner, bot_id: str):
    """在新进程中运行CrewRunner"""
    # 为每个runner实例创建新的trace_id
    log = get_logger_with_trace_id()
    try:
        await runner.run()
    except Exception as e:
        log.error(f"CrewRunner运行出错，Bot ID: {bot_id}, 错误: {str(e)}")
        raise


def start_crew_runner_process(bot_id: str, parent_bot_id: str, crew_config: Optional[dict] = None):
    """在新进程中启动CrewRunner

    Args:
        bot_id: Bot ID
        parent_bot_id: 父Bot ID
        crew_config: 从ManagerInitFlow生成的CR配置
    """
    runner = CrewRunner(
        bot_id=UUID(bot_id),
        parent_bot_id=UUID(parent_bot_id),
        crew_config=crew_config,  # 传递动态配置
    )
    asyncio.run(run_crew_runner(runner, bot_id))

def start_crew_manager_process(bot_id: str):
    """在新进程中启动CrewManager"""
    asyncio.run(run_crew_manager(bot_id))

class CrewMonitor:
    """监控器类，用于监听新的Opera和Bot创建事件，并动态启动相应的进程"""

    def __init__(self, signalr_url: str = "http://opera.nti56.com/signalRService"):
        self.log = get_logger_with_trace_id()
        self.signalr_client = OperaSignalRClient(url=signalr_url)
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
        
        # 新增：分别存储Manager和Runner的Bot ID集合
        self.managed_manager_bots: Set[str] = set()  # 存储已经启动了进程的Manager bot id
        self.managed_runner_bots: Set[str] = set()  # 存储已经启动了进程的Runner bot id

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

        # 断开SignalR连接
        await self.signalr_client.disconnect()

        # 停止所有进程
        with self.lock:
            for bot_id, process in self.processes.items():
                self.log.info(f"正在停止Bot {bot_id}的进程...")
                process.terminate()
                process.join()

        self.log.info("CrewMonitor已停止")

    async def _init_existing_bots(self):
        """初始化现有的Bots"""
        self.log.info("正在初始化现有Bots...")

        # 获取所有Bot
        result = self.bot_tool.run(action="get_all")

        try:
            status_code, bots_data = self.parser.parse_response(result)

            if status_code == 200:
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
            self.log.debug(f"使用现有Bot缓存，缓存时间: {self.bot_cache_time}，当前时间: {current_time}")
            return
            
        # 否则重新获取Bot列表
        try:
            result = self.bot_tool._run(action="get_all")
            status_code, bots_data = self.parser.parse_response(result)
            
            if status_code == 200:
                # 更新缓存和时间戳
                self.bot_cache = bots_data
                self.bot_cache_time = current_time
                self.log.debug(f"已更新Bot缓存，共{len(bots_data)}个Bot")
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
                    bot for bot in crew_manager_bots 
                    if not bot["isActive"] and bot["id"] not in self.managed_bots
                ]

                if new_crew_manager_bots:
                    self.log.info(f"发现{len(new_crew_manager_bots)}个新的符合条件的CrewManager Bot")

                    # 为每个新的符合条件的Bot启动CrewManager进程
                    for bot in new_crew_manager_bots:
                        await self._start_bot_manager(bot["id"], bot["name"])
                
                # 1.1 检查新的符合条件的Bot (Runner)
                new_crew_runner_bots = [
                    bot for bot in crew_runner_bots 
                    if not bot["isActive"] and bot["id"] not in self.managed_bots
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
            process = multiprocessing.Process(
                target=start_crew_runner_process, 
                args=(bot_id, parent_id)
            )
            process.start()

            # 记录进程和Bot
            self.processes[bot_id] = process
            self.managed_bots.add(bot_id)
            self.managed_runner_bots.add(bot_id)  # 更新Runner Bot集合

            # 记录重启时间
            self.restart_history[bot_id] = asyncio.get_event_loop().time()

            self.log.info(f"已为Bot {bot_id}启动CrewRunner进程，父Bot ID: {parent_id}")

    async def _periodic_check(self, interval: int = 500):
        """定期检查新的Bot"""
        while True:
            await self._check_bots()
            await asyncio.sleep(interval)


async def main():
    # 获取logger实例
    setup_logger(name="main")
    log = get_logger(__name__, log_file="logs/main.log")
    # 为main函数创建新的trace_id
    log = get_logger_with_trace_id()

    # 创建并启动监控器
    monitor = CrewMonitor()
    await monitor.start()

    # 启动定期检查任务
    check_task = asyncio.create_task(monitor._periodic_check())

    try:
        # 保持主程序运行
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        log.info("收到中断信号，正在停止...")
        # 取消定期检查任务
        check_task.cancel()
        # 停止监控器
        await monitor.stop()
        log.info("程序已停止")
    except Exception as e:
        log.error(f"程序运行出错: {str(e)}")
        # 取消定期检查任务
        check_task.cancel()
        # 停止监控器
        await monitor.stop()
        raise

if __name__ == "__main__":
    # 设置多进程启动方法
    multiprocessing.set_start_method('spawn')
    asyncio.run(main())