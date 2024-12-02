import asyncio
from Opera.Signalr.opera_signalr_client import OperaSignalRClient, MessageReceivedArgs
from loguru import logger
import sys


async def message_handler(message: MessageReceivedArgs):
    """处理接收到的消息"""
    logger.info(f"收到消息: {message.text}")
    # TODO: 实现发送消息的方法
    # await client.send_message(message.opera_id, f"复读: {message.text}")


async def main():
    # 创建SignalR客户端
    bot_id = "894c1763-22b2-418c-9a18-3c40b88d28bc"
    client = OperaSignalRClient(bot_id=bot_id)
    
    # 设置消息处理回调
    client.set_callback("on_message_received", message_handler)

    # 连接服务器
    await client.connect()
    
    # 等待连接成功
    while not client.is_connected():
        await asyncio.sleep(0.1)
    
    logger.info(f"Bot已启动，ID: {bot_id}")

    # 保持程序运行
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await client.disconnect()
        logger.info("Bot已停止")


if __name__ == "__main__":
    # 配置logger，添加进程名称
    logger.remove()  # 移除默认的处理器
    logger.add(
        sink=sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>simple_repeater</cyan>:{function}:{line} - {message}",
    )
    asyncio.run(main())