import asyncio
from Opera.Signalr.opera_message_processor import CrewManager
from loguru import logger

async def main():
    manager = CrewManager()
    try:
        await manager.start()
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await manager.stop()
        logger.info("程序已退出")

if __name__ == "__main__":
    asyncio.run(main()) 