from typing import List, Dict, Optional
from dataclasses import dataclass
from bot_manager.core.interfaces import IAgent

@dataclass
class Message:
    content: str
    sender: str
    receiver: Optional[str] = None  # None表示广播消息
    metadata: Dict = None

class ConversationManager:
    def __init__(self):
        self._conversations: Dict[str, Dict[str, IAgent]] = {}  # conv_id -> {agent_name: agent}
        
    async def create_conversation(self, agents_config: List[Dict]) -> str:
        """创建包含多个Agent的会话"""
        conv_id = self._generate_conv_id()
        agents = {}
        
        for config in agents_config:
            adapter = self._get_adapter(config["framework"])
            agent = await adapter.adapt(config)
            agents[agent.name] = agent
            
        self._conversations[conv_id] = agents
        return conv_id

    async def send_message(self, 
                         conv_id: str, 
                         message: str, 
                         from_agent: str, 
                         to_agent: Optional[str] = None) -> List[str]:
        """发送消息到特定Agent或广播"""
        if conv_id not in self._conversations:
            raise ValueError(f"Conversation {conv_id} not found")
            
        agents = self._conversations[conv_id]
        responses = []

        if to_agent:  # 定向消息
            if to_agent not in agents:
                raise ValueError(f"Agent {to_agent} not found in conversation")
                
            target_agent = agents[to_agent]
            adapted_message = await self._adapt_message(
                message,
                agents[from_agent],
                target_agent
            )
            
            await target_agent.send_message(adapted_message)
            response = await target_agent.get_response()
            responses.append(response)
            
        else:  # 广播消息
            for agent_name, agent in agents.items():
                if agent_name != from_agent:
                    adapted_message = await self._adapt_message(
                        message,
                        agents[from_agent],
                        agent
                    )
                    await agent.send_message(adapted_message)
                    response = await agent.get_response()
                    responses.append(response)
                    
        return responses

    async def _adapt_message(self, 
                           message: str, 
                           from_agent: IAgent, 
                           to_agent: IAgent) -> str:
        """处理消息格式转换"""
        # 检查能力兼容性
        if not self._check_capability_compatibility(from_agent, to_agent):
            raise IncompatibleAgentsError(
                f"Incompatible capabilities between {from_agent.name} and {to_agent.name}"
            )
            
        # 根据目标Agent的能力调整消息格式
        if "code_generation" in to_agent.capabilities:
            # 处理代码相关的特殊格式
            return self._format_code_message(message)
            
        if "function_call" in to_agent.capabilities:
            # 处理函数调用相关的格式
            return self._format_function_message(message)
            
        return message

    def _check_capability_compatibility(self, 
                                     from_agent: IAgent, 
                                     to_agent: IAgent) -> bool:
        """检查两个Agent之间的能力兼容性"""
        required_capabilities = self._get_required_capabilities(from_agent.capabilities)
        return all(cap in to_agent.capabilities for cap in required_capabilities)

    def get_conversation_state(self, conv_id: str) -> Dict:
        """获取会话状态"""
        if conv_id not in self._conversations:
            raise ValueError(f"Conversation {conv_id} not found")
            
        return {
            "agents": list(self._conversations[conv_id].keys()),
            "active": True  # 可以添加更多状态信息
        }

    def _generate_conv_id(self) -> str:
        """生成唯一的会话ID"""
        # 实现会话ID生成逻辑
        pass

    def _get_adapter(self, framework: str) -> "IAgentAdapter":
        """获取对应框架的适配器"""
        # 实现适配器获取逻辑
        pass