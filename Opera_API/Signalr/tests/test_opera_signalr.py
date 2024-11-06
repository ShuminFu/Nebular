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

def test_system_shutdown():
    shutdown_received = False
    client = None
    
    async def on_system_shutdown():
        nonlocal shutdown_received
        shutdown_received = True
    
    def run_client():
        nonlocal client
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        client = OperaSignalRClient()
        client.set_callback("on_system_shutdown", on_system_shutdown)
        loop.run_until_complete(client.connect())
    
    thread = threading.Thread(target=run_client)
    thread.daemon = True
    thread.start()
    
    # 模拟接收系统关闭信号
    time.sleep(1)
    # TODO: 触发系统关闭事件
    
    assert shutdown_received, "系统关闭测试失败：未收到关闭回调"

def test_opera_created():
    opera_created = False
    client = None
    test_opera_data = {
        "operaId": "550e8400-e29b-41d4-a716-446655440000",
        "parentId": None,
        "name": "测试Opera",
        "description": "测试描述",
        "databaseName": "test_db"
    }
    
    async def on_opera_created(args):
        nonlocal opera_created
        assert args["operaId"] == test_opera_data["operaId"]
        assert args["name"] == test_opera_data["name"]
        opera_created = True
    
    def run_client():
        nonlocal client
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        client = OperaSignalRClient()
        client.set_callback("on_opera_created", on_opera_created)
        loop.run_until_complete(client.connect())
    
    thread = threading.Thread(target=run_client)
    thread.daemon = True
    thread.start()
    
    # 等待回调（最多等待3秒）
    start_time = time.time()
    while not opera_created and time.time() - start_time < 3:
        time.sleep(0.1)
    
    assert opera_created, "Opera创建测试失败：未收到创建回调"

def test_message_received():
    message_received = False
    client = None
    test_message = {
        "OperaId": "550e8400-e29b-41d4-a716-446655440000",
        "ReceiverStaffIds": ["4a4857d6-4664-452e-a37c-80a628ca28a0"],
        "Index": 1,
        "Time": "2024-03-20T10:00:00Z",
        "StageIndex": 1,
        "SenderStaffId": "550e8400-e29b-41d4-a716-446655440001",
        "IsNarratage": False,
        "IsWhisper": False,
        "Text": "测试消息",
        "Tags": "test",
        "MentionedStaffIds": []
    }
    
    async def on_message_received(args):
        nonlocal message_received
        assert args["OperaId"] == test_message["OperaId"]
        assert args["Text"] == test_message["Text"]
        message_received = True
    
    def run_client():
        nonlocal client
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        client = OperaSignalRClient()
        client.set_callback("on_message_received", on_message_received)
        loop.run_until_complete(client.connect())
    
    thread = threading.Thread(target=run_client)
    thread.daemon = True
    thread.start()
    
    # 等待回调（最多等待3秒）
    start_time = time.time()
    while not message_received and time.time() - start_time < 3:
        time.sleep(0.1)
    
    assert message_received, "消息接收测试失败：未收到消息回调"

