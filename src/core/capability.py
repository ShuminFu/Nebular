from typing import Dict, Callable, Any
from functools import wraps

class CapabilityManager:
    """
    能力管理器，负责管理和执行Agent的各种能力
    
    Attributes:
        _capabilities (Dict[str, Callable]): 已注册的能力字典
    """
    
    def __init__(self):
        self._capabilities: Dict[str, Callable] = {}
    
    def register_capability(self, name: str, function: Callable) -> None:
        """
        注册新能力
        
        Args:
            name (str): 能力名称
            function (Callable): 能力实现函数
        """
        if name in self._capabilities:
            raise ValueError(f"能力 {name} 已存在")
        
        @wraps(function)
        def wrapper(*args, **kwargs):
            # TODO: 添加能力执行前后的处理逻辑
            return function(*args, **kwargs)
            
        self._capabilities[name] = wrapper
    
    def execute_capability(self, name: str, *args, **kwargs) -> Any:
        """
        执行指定能力
        
        Args:
            name (str): 能力名称
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            Any: 能力执行结果
        """
        if name not in self._capabilities:
            raise ValueError(f"能力 {name} 不存在")
            
        return self._capabilities[name](*args, **kwargs) 