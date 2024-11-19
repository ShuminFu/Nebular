from abc import ABC, abstractmethod
from typing import List
from ..capabilities.base import IBotCapability

class IBotFactory(ABC):
    @abstractmethod
    async def create_bot(self, capabilities: List[IBotCapability]) -> str:
        pass
    
    @abstractmethod
    async def destroy_bot(self, bot_id: str) -> None:
        pass

class BaseBotFactory(IBotFactory):
    def __init__(self):
        self.bots = {}
        
    async def create_bot(self, capabilities: List[IBotCapability]) -> str:
        # 基础实现
        pass
        
    async def destroy_bot(self, bot_id: str) -> None:
        # 基础实现
        pass 