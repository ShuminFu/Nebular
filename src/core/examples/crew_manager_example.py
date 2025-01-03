import asyncio
import multiprocessing
from uuid import UUID
from src.nebular_core.logger_config import get_logger, get_logger_with_trace_id
from src.crewai_core.tools.opera_api.bot_api_tool import BotTool
from src.nebular_core.crew_process import CrewManager, CrewRunner
from src.nebular_core.api_response_parser import ApiResponseParser
import backoff  # 需要添加到requirements.txt

# 获取logger实例
logger = get_logger(__name__, log_file="logs/crew_manager.log")

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
        # 获取Bot信息以读取defaultTags
        bot_info = bot_tool.run(action="get", bot_id=bot_id)
        log.info(f"获取Bot {bot_id} 信息: {bot_info}")

        # 解析Bot信息
        _, bot_data = parser.parse_response(bot_info)
        default_tags = parser.parse_default_tags(bot_data)
        child_bots = parser.get_child_bots(default_tags)
        log.info(f"从defaultTags获取到的子Bot列表: {child_bots}")

        # 检查每个子Bot的状态并启动未激活的Bot
        for child_bot_id in child_bots:
            try:
                # 获取子Bot状态
                child_bot_info = bot_tool.run(action="get", bot_id=child_bot_id)
                _, child_bot_data = parser.parse_response(child_bot_info)

                if not child_bot_data.get("isActive", True):
                    # 为未激活的子Bot创建CrewRunner进程
                    process = multiprocessing.Process(
                        target=start_crew_runner_process,
                        args=(child_bot_id, {
                            "agents": [
                                {
                                    "name": "Default Agent",
                                    "role": "Assistant",
                                    "goal": "Help with tasks",
                                    "backstory": "I am an AI assistant"
                                }
                            ],
                            "max_retries": 3,  # 添加重试次数配置
                            "retry_delay": 5    # 添加重试延迟配置
                        })
                    )
                    process.start()
                    crew_processes.append(process)
                    log.info(f"已为子Bot {child_bot_id} 启动CrewRunner进程")
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
        # 停止所有CrewRunner进程
        for process in crew_processes:
            process.terminate()
            process.join()
        log.info(f"CrewManager和所有CrewRunner已停止，Bot ID: {bot_id}")
    except Exception as e:
        log.error(f"CrewManager运行出错，Bot ID: {bot_id}, 错误: {str(e)}")
        # 确保清理所有进程
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


def start_crew_runner_process(bot_id: str, config: dict):
    """在新进程中启动CrewRunner"""
    runner = CrewRunner(config=config, bot_id=UUID(bot_id))
    asyncio.run(run_crew_runner(runner, bot_id))

def start_crew_manager_process(bot_id: str):
    """在新进程中启动CrewManager"""
    asyncio.run(run_crew_manager(bot_id))

async def main():
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
            crew_manager_bots = [
                bot for bot in bots_data
                if "测试" in bot["name"] and not bot["isActive"]
            ]
            # TODO: 这里可以把tag也加入到CrewManager的初始化信息中。
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
