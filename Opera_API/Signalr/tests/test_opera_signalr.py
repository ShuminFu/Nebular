import threading
import time
from uuid import UUID
from ..opera_signalr_client import OperaSignalRClient

TEST_BOT_ID = "4a4857d6-4664-452e-a37c-80a628ca28a0"

def test_connection():
    connection_successful = False
    client = None
    
    async def on_hello():
        nonlocal connection_successful
        connection_successful = True
    
    def run_client():
        nonlocal client
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        client = OperaSignalRClient()
        client.set_callback("on_hello", on_hello)
        
        # 在同一个事件循环中执行连接和设置 bot_id
        loop.run_until_complete(asyncio.gather(
            client.connect(),
            client.set_bot_id(UUID(TEST_BOT_ID))
        ))
    
    # 启动客户端线程
    thread = threading.Thread(target=run_client)
    thread.daemon = True
    thread.start()
    
    # 等待连接建立和回调（最多等待3秒）
    start_time = time.time()
    while not connection_successful and time.time() - start_time < 3:
        time.sleep(0.1)
    
    assert connection_successful, "连接测试失败：未收到 Hello 回调" 