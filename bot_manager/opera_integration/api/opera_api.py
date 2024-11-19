from abc import ABC, abstractmethod
from typing import Any

class IOperaAPI(ABC):
    @abstractmethod
    async def create_conversation(self, request: Any) -> Any:
        pass
    
    @abstractmethod
    async def get_conversation(self, conversation_id: str) -> Any:
        pass
    
    @abstractmethod
    async def send_message(self, request: Any) -> Any:
        pass

class OperaAPIClient(IOperaAPI):
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        
    async def create_conversation(self, request: Any) -> Any:
        # 实现创建对话
        pass 