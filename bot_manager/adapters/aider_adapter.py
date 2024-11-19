from aider import AiderAgent
from ..core.interfaces import IBot, IBotAdapter
from typing import Dict, Any, Optional

class AiderBotAdapter(IBotAdapter):
    async def adapt(self, config: Dict[str, Any]) -> IBot:
        aider_bot = await self._create_aider_bot(config)
        return AiderBotWrapper(aider_bot)

class AiderBotWrapper(IBot):
    def __init__(self, aider_bot):
        self._bot = aider_bot
    
    async def send_message(self, message: str, **kwargs) -> None:
        await self._bot.send_message(message)
        
    async def get_response(self) -> str:
        return await self._bot.get_response()
        
    @property
    def capabilities(self) -> Dict[str, Any]:
        return {
            "code_generation": True,
            "code_editing": True
        }
        
    async def invoke_capability(self, capability_name: str, **kwargs) -> Any:
        raise NotImplementedError(f"Capability {capability_name} not supported")