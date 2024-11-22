from typing import Dict, List, Optional
from uuid import UUID, uuid4

class AgentTemplate:
    """
    Agent模板类，定义Agent的配置和行为模式
    
    Attributes:
        id (UUID): 模板唯一标识
        prompt_config (Dict): 提示词配置
        llm_config (Dict): LLM配置
        framework_type (str): 使用的框架类型
        capabilities (List[str]): 能力列表
    """
    
    def __init__(self, 
                 prompt_config: Dict,
                 llm_config: Dict,
                 framework_type: str,
                 capabilities: List[str]):
        self.id = uuid4()
        self.prompt_config = prompt_config
        self.llm_config = llm_config
        self.framework_type = framework_type
        self.capabilities = capabilities
    
    def apply_to_agent(self, agent: 'Agent') -> None: # type: ignore
        """
        将模板配置应用到Agent实例
        
        Args:
            agent (Agent): 目标Agent实例
        """
        # 注册能力
        for capability in self.capabilities:
            # TODO: 实现能力注册逻辑
            pass
        
        # 应用LLM配置
        # TODO: 实现LLM配置逻辑
        pass 