import asyncio
import multiprocessing
from uuid import UUID
from src.core.logger_config import get_logger, get_logger_with_trace_id, setup_logger
from src.crewai_ext.tools.opera_api.bot_api_tool import BotTool
from src.core.crew_process import CrewManager, CrewRunner
from src.core.parser.api_response_parser import ApiResponseParser
from src.core.bot_api_helper import (
    fetch_bot_data,
    fetch_staff_data,
    create_child_bot,
    update_parent_bot_tags,
    get_child_bot_opera_ids,
)

from typing import Optional
import backoff



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
                    await update_parent_bot_tags(bot_tool, bot_id, existing_child_bots, log)

        # 4. 启动未激活的ChildBots
        for child_bot_id in existing_child_bots:
            try:
                # 获取子Bot状态
                child_bot_data = await fetch_bot_data(bot_tool, child_bot_id, log)

                if not child_bot_data.get("isActive", True):
                    # 获取子Bot的CR配置
                    child_tags = parser.parse_default_tags(child_bot_data)
                    crew_config = child_tags.get("crew_config", {})

                    # 为未激活的子Bot创建CrewRunner进程
                    process = multiprocessing.Process(
                        target=start_crew_runner_process,
                        args=(
                            child_bot_id,
                            bot_id,
                            # crew_config,  # 传递从childbot中获取的动态配置
                        ),
                    )
                    process.start()
                    crew_processes.append(process)
                    log.info(f"已为子Bot {child_bot_id} 启动CrewRunner进程，父Bot ID: {bot_id}")
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

async def main():
    # 获取logger实例
    setup_logger(name="main")
    log = get_logger(__name__, log_file="logs/main.log")
    # 为main函数创建新的trace_id
    log = get_logger_with_trace_id()
    # 创建BotTool实例
    bot_tool = BotTool()
    parser = ApiResponseParser()

    # 获取所有Bot
    result = bot_tool.run(action="get_all")
    log.info(f"获取所有Bot结果: {result}")

    # 存储所有进程的列表
    processes = []

    try:
        status_code, bots_data = parser.parse_response(result)

        if status_code == 200:
            # 过滤符合条件的Bot
            crew_manager_bots = [bot for bot in bots_data if "测试" in bot["name"] and not bot["isActive"]]
            log.info("符合条件的Bot列表:")
            for bot in crew_manager_bots:
                log.info(f"ID: {bot['id']}, Name: {bot['name']}, Description: {bot['description']}")

                # 为每个Bot创建新进程
                process = multiprocessing.Process(
                    target=start_crew_manager_process,
                    args=(bot['id'],)
                )
                process.start()
                processes.append(process)
                log.info(f"已为Bot {bot['id']}启动CrewManager进程")

            # 等待所有进程
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                log.info("正在停止所有进程...")
                for process in processes:
                    process.terminate()
                    process.join()
                log.info("所有进程已停止")
        else:
            log.error(f"API请求失败，状态码: {status_code}")
    except Exception as e:
        log.error(f"处理结果时出错: {str(e)}")
        # 确保清理所有进程
        for process in processes:
            process.terminate()
            process.join()

if __name__ == "__main__":
    # 设置多进程启动方法
    multiprocessing.set_start_method('spawn')
    asyncio.run(main())