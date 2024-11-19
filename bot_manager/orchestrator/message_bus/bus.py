from abc import ABC, abstractmethod
from typing import Callable, Any
from dataclasses import dataclass

@dataclass
class Message:
    id: str
    content: Any
    sender: str
    receiver: str
    priority: int = 0

class IMessageBus(ABC):
    @abstractmethod
    async def send_message(self, message: Message) -> None:
        pass
    
    @abstractmethod
    async def broadcast(self, message: Message) -> None:
        pass
    
    @abstractmethod
    def subscribe(self, bot_id: str, handler: Callable) -> None:
        pass

class DirectMessageBus(IMessageBus):
    def __init__(self):
        self.subscribers = {}
        self.message_queue = PriorityQueue()
        
    async def send_message(self, message: Message) -> None:
        # 实现消息发送逻辑
        pass 