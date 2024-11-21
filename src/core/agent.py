from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID
from .agent_template import AgentTemplate
from .capability import CapabilityManager

class AgentState(Enum):
    """Agent状态枚举"""
    INITIALIZED = "initialized"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"

class Agent:
    """
    Agent核心类，代表一个AI助手实例
    
    Attributes:
        name (str): Agent名称
        template (AgentTemplate): Agent使用的模板
        state (AgentState): 当前状态
        _capability_manager (CapabilityManager): 能力管理器
    """
    
    def __init__(self, name: str, template: AgentTemplate):
        self.name = name
        self.template = template
        self.state = AgentState.INITIALIZED
        self._capability_manager = CapabilityManager()
        
        # 应用模板配置
        self.template.apply_to_agent(self)
    
    def start(self) -> bool:
        """启动Agent"""
        try:
            self.state = AgentState.RUNNING
            return True
        except Exception as e:
            self.state = AgentState.ERROR
            raise e
    
    def stop(self) -> bool:
        """停止Agent"""
        try:
            self.state = AgentState.STOPPED
            return True
        except Exception as e:
            self.state = AgentState.ERROR
            raise e
    
    def communicate(self, message: str) -> str:
        """
        处理接收到的消息
        
        Args:
            message (str): 接收到的消息
            
        Returns:
            str: 响应消息
        """
        if self.state != AgentState.RUNNING:
            raise RuntimeError("Agent不在运行状态")
        
        # TODO: 实现具体的消息处理逻辑
        return f"Echo: {message}" 