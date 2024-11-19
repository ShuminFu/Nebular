from typing import Dict, Optional
from .interfaces import IBot, IBotAdapter

class BotFactory:
    """Bot工厂类，负责创建适配后的Bot"""
    
    def __init__(self):
        self._adapters: Dict[str, IBotAdapter] = {}
        
    def register_adapter(self, framework: str, adapter: IBotAdapter) -> None:
        """注册框架适配器"""
        self._adapters[framework] = adapter
        
    async def create_bot(self, config: Dict) -> IBot:
        """创建指定框架的Bot"""
        framework = config.get("framework")
        if framework not in self._adapters:
            raise ValueError(f"Unsupported framework: {framework}")
            
        adapter = self._adapters[framework]
        return await adapter.adapt(config) 