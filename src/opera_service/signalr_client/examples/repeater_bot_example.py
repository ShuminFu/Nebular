import asyncio
from src.opera_core.signalr_client.opera_signalr_client import OperaSignalRClient, MessageReceivedArgs
from loguru import logger
import sys


async def message_handler(message: MessageReceivedArgs):
    """处理接收到的消息"""
    logger.info(f"收到消息: {message.text}")
    # 这里预留实现发送消息的方法，但是SignalR Server暂不支持直接发送消息，需要通过调用Opera API来发送消息。
    # 唯一支持client.send的方法是SetBotID
    pass



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
            if not client.is_connected():
                logger.error("SignalR连接已断开，尝试重新连接...")
                try:
                    await client.disconnect()  # 确保清理旧连接
                    await client.connect()
                    await asyncio.sleep(5)  # 重连间隔
                    continue
                except Exception as e:
                    logger.error(f"重连失败: {e}")
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await client.disconnect()
        logger.info("Bot已停止")
    except Exception as e:
        logger.error(f"运行时发生错误: {e}")
        await client.disconnect()
        raise


if __name__ == "__main__":
    # 配置logger，添加进程名称
    logger.remove()  # 移除默认的处理器
    logger.add(
        sink=sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>simple_repeater</cyan>:{function}:{line} - {message}",
    )
    asyncio.run(main())