import asyncio
from uuid import uuid4
from loguru import logger
from Opera.Signalr.opera_message_processor import CrewRunner


async def main():
    # 创建最简单的Crew配置
    crew_config = {
        'as_staff': False,  # 先用最简单的Bot模式
        'agents': [
            {
                'name': 'EchoBot',
                'role': '复读机器人',
                'goal': '复读收到的消息',
                'backstory': '我是一个简单的复读机器人',
                'task': '复读用户的消息'
            }
        ]
    }

    # 创建一个测试用的Opera ID和Crew ID
    opera_id = uuid4()
    crew_id = uuid4()

    logger.info(f"开始测试 Crew {crew_id} for Opera {opera_id}")

    # 直接创建和运行CrewRunner
    crew_runner = CrewRunner(crew_config, opera_id, crew_id)

    try:
        # 运行Crew
        await crew_runner.run()
    except KeyboardInterrupt:
        logger.info("收到终止信号，正在停止Crew...")
        await crew_runner.stop()
    except Exception as e:
        logger.exception(f"测试过程出错: {e}")


if __name__ == "__main__":
    asyncio.run(main())