from typing import Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # SignalR配置
    SIGNALR_URL = os.getenv("SIGNALR_URL")
    
    # Bot Factory配置
    BOT_POOL_SIZE = int(os.getenv("BOT_POOL_SIZE", "10"))
    BOT_TIMEOUT = int(os.getenv("BOT_TIMEOUT", "300"))
    
    # Opera集成配置
    OPERA_API_URL = os.getenv("OPERA_API_URL")
    OPERA_API_KEY = os.getenv("OPERA_API_KEY")
    
    # 消息同步配置
    SYNC_BATCH_SIZE = int(os.getenv("SYNC_BATCH_SIZE", "100"))
    SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL", "1")) 