import asyncio
from uuid import UUID
from contextlib import suppress
from opera_signalr_client import OperaSignalRClient


async def on_hello():
    print("Connected!")


async def on_message(msg):
    print(f"收到消息: {msg.text}")


async def main():
    client = OperaSignalRClient()

    # 设置回调函数
    client.set_callback("on_hello", on_hello)
    client.set_callback("on_message_received", on_message)

    # 连接服务器并设置Bot ID
    await asyncio.gather(
        client.connect(),
        client.set_bot_id(UUID("your-bot-id")),
        client.set_snitch_mode(True)
    )


if __name__ == "__main__":
    with suppress(KeyboardInterrupt, asyncio.CancelledError):
        asyncio.run(main())