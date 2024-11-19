from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

class IBot(ABC):
    """统一的Bot接口定义"""
    
    @abstractmethod
    async def send_message(self, message: str, **kwargs) -> None:
        """发送消息到Bot"""
        pass
    
    @abstractmethod
    async def get_response(self) -> str:
        """获取Bot的响应"""
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> Dict[str, Any]:
        """获取Bot的能力描述"""
        pass
    
    @abstractmethod
    async def invoke_capability(self, capability_name: str, **kwargs) -> Any:
        """调用特定能力"""
        pass

class IBotAdapter(ABC):
    """Bot适配器接口"""
    
    @abstractmethod
    async def adapt(self, config: Dict[str, Any]) -> IBot:
        """将框架特定的Bot适配为统一接口"""
        pass