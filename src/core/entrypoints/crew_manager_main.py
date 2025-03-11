import asyncio
import multiprocessing
import os
from uuid import UUID
from src.core.logger_config import get_logger, get_logger_with_trace_id, setup_logger
from src.crewai_ext.tools.opera_api.bot_api_tool import BotTool
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

from typing import Optional, Dict, Set
import backoff
import threading

# 从环境变量读取Bot名称过滤条件，默认为"CM"
BOT_NAME_FILTER = os.environ.get("BOT_NAME_FILTER", "前端")



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
    crew_processes = []
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
        for process in crew_processes:
            process.terminate()
            process.join()
        log.info(f"CrewManager和所有CrewRunner已停止，Bot ID: {bot_id}")
    except Exception as e:
        log.error(f"CrewManager运行出错，Bot ID: {bot_id}, 错误: {str(e)}")
        for process in crew_processes:
            process.terminate()
            process.join()
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
        self.parser = ApiResponseParser()
        self.processes: Dict[str, multiprocessing.Process] = {}  # 存储所有进程，key为bot_id
        self.managed_bots: Set[str] = set()  # 存储已经启动了进程的bot id
        self.lock = threading.Lock()  # 用于保护共享资源

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
                crew_manager_bots = [bot for bot in bots_data if BOT_NAME_FILTER in bot["name"] and not bot["isActive"]]

                if crew_manager_bots:
                    self.log.info(f"发现{len(crew_manager_bots)}个符合条件的Bot")

                    # 为每个符合条件的Bot启动或重启CrewManager进程
                    for bot in crew_manager_bots:
                        await self._start_bot_manager(bot["id"], bot["name"])
            else:
                self.log.error(f"获取Bot列表失败，状态码: {status_code}")
        except Exception as e:
            self.log.error(f"初始化现有Bots时出错: {str(e)}")

    async def _on_opera_created(self, opera_args: OperaCreatedArgs):
        """处理新建Opera事件"""
        self.log.info(f"收到新建Opera事件: {opera_args.name}, ID: {opera_args.opera_id}")

        try:
            # 获取Opera的ID
            opera_id_str = str(opera_args.opera_id)

            # 检查该Opera是否已有符合条件的crew_manager_bots作为staff
            staff_result = self.bot_tool.run(action="get_opera_staffs", opera_id=opera_id_str)
            staff_status, staff_data = self.parser.parse_response(staff_result)

            if staff_status != 200:
                self.log.error(f"获取Opera {opera_args.name} 的Staff信息失败，状态码: {staff_status}")
                return

            # 检查是否有crew_manager_bots作为staff
            crew_manager_staffs = []
            if staff_data and isinstance(staff_data, list):  # 确保staff_data是一个列表
                crew_manager_staffs = [
                    staff for staff in staff_data if staff.get("botId") and BOT_NAME_FILTER in (staff.get("botName") or "")
                ]

            if crew_manager_staffs:
                self.log.info(f"Opera {opera_args.name} 已有符合条件的crew_manager_bots作为staff")

                # 检查这些Bot是否已经在管理列表中
                with self.lock:
                    for staff in crew_manager_staffs:
                        bot_id = staff.get("botId")
                        if bot_id and bot_id not in self.managed_bots:
                            self.log.info(f"为已有的Bot {staff.get('botName')} (ID: {bot_id})启动进程")
                            await self._start_bot_manager(bot_id, staff.get("botName"))
                return  # 有符合条件的crew_manager_bots作为staff，直接返回

            # 如果没有符合条件的crew_manager_bots，则创建新Bot
            self.log.info(f"为Opera {opera_args.name} (ID: {opera_args.opera_id})创建新的Bot...")

            # 创建Bot的API调用
            bot_name = f"前端-{opera_args.name}"
            new_bot_params = {
                "action": "create",
                "opera_id": opera_id_str,
                "name": bot_name,
                # 其他参数按需添加
            }

            new_bot_result = self.bot_tool.run(**new_bot_params)
            status_code, new_bot_data = self.parser.parse_response(new_bot_result)

            if status_code == 200:
                self.log.info(f"成功创建Bot: {new_bot_data['name']} (ID: {new_bot_data['id']})")

                # 确保不重复启动进程
                with self.lock:
                    if new_bot_data["id"] not in self.managed_bots:
                        await self._start_bot_manager(new_bot_data["id"], new_bot_data["name"])
            else:
                self.log.error(f"创建Bot失败，状态码: {status_code}")

        except Exception as e:
            self.log.error(f"处理Opera创建事件时出错: {str(e)}")

    async def _check_bots(self):
        """定期检查新的Bot和已管理但可能非活跃的Bot"""
        # 获取所有Bot
        result = self.bot_tool._run(action="get_all")

        try:
            status_code, bots_data = self.parser.parse_response(result)

            if status_code == 200:
                # 1. 检查新的符合条件的Bot
                new_crew_manager_bots = [bot for bot in bots_data if BOT_NAME_FILTER in bot["name"] and not bot["isActive"]]

                if new_crew_manager_bots:
                    self.log.info(f"发现{len(new_crew_manager_bots)}个新的符合条件的Bot")

                    # 为每个新的符合条件的Bot启动CrewManager进程
                    for bot in new_crew_manager_bots:
                        await self._start_bot_manager(bot["id"], bot["name"])

                # 2. 检查已管理但可能已经在Opera中变为非活跃的Bot
                with self.lock:
                    managed_bot_ids = self.managed_bots.copy()

                # 获取当前在Opera中活跃的Bot ID列表
                active_bot_ids = {bot["id"] for bot in bots_data if bot["isActive"]}

                # 找出已管理但在Opera中显示为非活跃的Bot
                inactive_managed_bots = []
                for bot in bots_data:
                    if bot["id"] in managed_bot_ids and not bot["isActive"]:
                        inactive_managed_bots.append(bot)

                if inactive_managed_bots:
                    self.log.info(f"发现{len(inactive_managed_bots)}个已管理但在Opera中显示为非活跃的Bot")

                    # 重新启动这些Bot的CrewManager进程
                    for bot in inactive_managed_bots:
                        self.log.info(f"Bot {bot['name']}(ID: {bot['id']})在Opera中显示为非活跃，将重新启动...")
                        with self.lock:
                            # 从管理列表中移除，以便_start_bot_manager可以重新启动它
                            if bot["id"] in self.managed_bots:
                                self.managed_bots.remove(bot["id"])

                            # 如果存在相关进程，终止它
                            if bot["id"] in self.processes:
                                process = self.processes[bot["id"]]
                                if process.is_alive():
                                    self.log.info(f"终止Bot {bot['id']}的现有进程")
                                    process.terminate()
                                    process.join()
                                del self.processes[bot["id"]]

                        # 重新启动
                        await self._start_bot_manager(bot["id"], bot["name"])
            else:
                self.log.error(f"获取Bot列表失败，状态码: {status_code}")
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

            self.log.info(f"已为Bot {bot_id}启动CrewManager进程")

    async def _periodic_check(self, interval: int = 5):
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