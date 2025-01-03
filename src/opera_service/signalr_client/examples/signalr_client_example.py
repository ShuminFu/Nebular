import asyncio
from uuid import UUID
from contextlib import suppress
from src.opera_service.signalr_client.opera_signalr_client import OperaSignalRClient

BOT_ID = "4a4857d6-4664-452e-a37c-80a628ca28a0"


async def on_hello():
    print("Connected!")


async def on_message(msg):
    print(f"收到消息: {msg.text}")


async def handle_opera_created(opera_args):
    print(f"处理Opera创建: {opera_args}")


async def maintain_connection(client: OperaSignalRClient):
    while True:
        try:
            await client.connect()
        except Exception as e:
            print(f"连接断开，5秒后重试: {str(e)}")
            await asyncio.sleep(5)


async def main():
    client = OperaSignalRClient()

    # 设置回调函数
    client.set_callback("on_hello", on_hello)
    client.set_callback("on_message_received", on_message)
    client.set_callback("on_opera_created", handle_opera_created)
    # 连接服务器并设置Bot ID
    connect_task = asyncio.create_task(maintain_connection(client))
    await asyncio.gather(
        connect_task,
        client.set_bot_id(UUID(BOT_ID)),
        client.set_snitch_mode(True)
    )


if __name__ == "__main__":
    with suppress(KeyboardInterrupt, asyncio.CancelledError):
        asyncio.run(main())
