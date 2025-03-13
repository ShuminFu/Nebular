"""
该模块包含用于启动不同类型Crew进程的函数。
将这些函数放在单独的模块中可以避免循环导入问题。
"""

import asyncio
import multiprocessing
from uuid import UUID
from src.core.logger_config import get_logger_with_trace_id
from src.crewai_ext.tools.opera_api.bot_api_tool import BotTool
from src.core.crew_process import CrewProcessInfo
from src.core.crew_bots.crew_manager import CrewManager
from src.core.crew_bots.crew_runner import CrewRunner
from src.core.parser.api_response_parser import ApiResponseParser
from src.core.bot_api_helper import (
    fetch_bot_data,
    fetch_staff_data,
    create_child_bot,
    update_parent_bot_tags,
    get_child_bot_opera_ids,
    get_child_bot_staff_info,
)
from typing import Optional
import backoff


@backoff.on_exception(backoff.expo, (asyncio.TimeoutError, ConnectionError), max_tries=3, max_time=300)
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


@backoff.on_exception(backoff.expo, (asyncio.TimeoutError, ConnectionError), max_tries=3, max_time=300)
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
