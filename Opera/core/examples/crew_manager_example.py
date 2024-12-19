import asyncio
import multiprocessing
from uuid import UUID
from loguru import logger
from ai_core.tools.opera_api.bot_api_tool import BotTool
from Opera.core.crew_process import CrewManager, CrewRunner
from Opera.core.bot_response_parser import BotResponseParser



async def run_crew_manager(bot_id: str):
    """为单个Bot运行CrewManager"""
    manager = CrewManager()
    manager.bot_id = UUID(bot_id)
    bot_tool = BotTool()
    crew_processes = []
    parser = BotResponseParser()
    
    try:
        # 获取Bot信息以读取defaultTags
        bot_info = bot_tool.run(action="get", bot_id=bot_id)
        logger.info(f"获取Bot {bot_id} 信息: {bot_info}")
        
        # 解析Bot信息
        _, bot_data = parser.parse_response(bot_info)
        default_tags = parser.parse_default_tags(bot_data)
        child_bots = parser.get_child_bots(default_tags)
        logger.info(f"从defaultTags获取到的子Bot列表: {child_bots}")
        
        # 检查每个子Bot的状态并启动未激活的Bot
        for child_bot_id in child_bots:
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
                        ]
                    }) # TODO: CrewRunner的初始化参数可以让CrewManager来决定或者从Description，Tags，Roles中获取。
                )
                process.start()
                crew_processes.append(process)
                logger.info(f"已为子Bot {child_bot_id} 启动CrewRunner进程")
        
        # 在启动子进程后设置SignalR连接
        await manager.setup()
        logger.info(f"CrewManager已启动，Bot ID: {bot_id}")
        
        # 运行CrewManager
        await manager.run()
            
    except asyncio.TimeoutError:
        logger.error(f"Bot {bot_id} 等待连接超时")
        raise
    except KeyboardInterrupt:
        await manager.stop()
        # 停止所有CrewRunner进程
        for process in crew_processes:
            process.terminate()
            process.join()
        logger.info(f"CrewManager和所有CrewRunner已停止，Bot ID: {bot_id}")
    except Exception as e:
        logger.error(f"CrewManager运行出错，Bot ID: {bot_id}, 错误: {str(e)}")
        # 确保清理所有进程
        for process in crew_processes:
            process.terminate()
            process.join()
        raise

def start_crew_runner_process(bot_id: str, config: dict):
    """在新进程中启动CrewRunner"""
    async def run_crew_runner():
        runner = CrewRunner(config=config, bot_id=UUID(bot_id))
        try:
            await runner.run()
        except Exception as e:
            logger.error(f"CrewRunner运行出错，Bot ID: {bot_id}, 错误: {str(e)}")
            raise
    
    asyncio.run(run_crew_runner())

def start_crew_manager_process(bot_id: str):
    """在新进程中启动CrewManager"""
    asyncio.run(run_crew_manager(bot_id))

async def main():
    # 创建BotTool实例
    bot_tool = BotTool()
    parser = BotResponseParser()
    
    # 获取所有Bot
    result = bot_tool.run(action="get_all")
    logger.info(f"获取所有Bot结果: {result}")
    
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
            logger.info("符合条件的Bot列表:")
            for bot in crew_manager_bots:
                logger.info(f"ID: {bot['id']}, Name: {bot['name']}, Description: {bot['description']}")
                
                # 为每个Bot创建新进程
                process = multiprocessing.Process(
                    target=start_crew_manager_process,
                    args=(bot['id'],)
                )
                process.start()
                processes.append(process)
                logger.info(f"已为Bot {bot['id']}启动新进程")
            
            # 等待所有进程
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("正在停止所有进程...")
                for process in processes:
                    process.terminate()
                    process.join()
                logger.info("所有进程已停止")
        else:
            logger.error(f"API请求失败，状态码: {status_code}")
    except Exception as e:
        logger.error(f"处理结果时出错: {str(e)}")
        # 确保清理所有进程
        for process in processes:
            process.terminate()
            process.join()

if __name__ == "__main__":
    # 设置多进程启动方法
    multiprocessing.set_start_method('spawn')
    asyncio.run(main()) 