from typing import Dict, Any
import autogen
from bot_manager.core.interfaces import IBot, IBotAdapter

class AutogenBotAdapter(IBotAdapter):
    async def adapt(self, config: Dict[str, Any]) -> IBot:
        # 从配置文件加载 LLM 配置
        config_list = autogen.config_list_from_json(
            "config/OAI_COMPATIBLE_CFG.json",
            filter_dict={
                "model": {
                    "gpt-4o",
                    "gpt-4o-mini",
                },
            },
        )
        
        llm_config = {"config_list": config_list, "cache_seed": 42}
        config["llm_config"] = llm_config  # 注入 LLM 配置
        
        bot_type = config.get("bot_type", "assistant")
        if bot_type == "user_proxy":
            bot = await self._create_user_proxy(config)
        else:
            bot = await self._create_assistant(config)
            
        return AutogenBotWrapper(bot, bot_type)

    async def _create_user_proxy(self, config: Dict[str, Any]) -> Any:
        return autogen.UserProxyAgent(
            name=config.get("name", "user_proxy"),
            human_input_mode="NEVER",
            max_consecutive_auto_reply=config.get("max_consecutive_auto_reply", 10),
            code_execution_config={
                "work_dir": config.get("work_dir", "workspace"),
                "use_docker": config.get("use_docker", False),
            }
        )

    async def _create_assistant(self, config: Dict[str, Any]) -> Any:
        return autogen.AssistantAgent(
            name=config.get("name", "assistant"),
            llm_config=config.get("llm_config", {})
        )

class AutogenBotWrapper(IBot):
    def __init__(self, autogen_bot, bot_type: str):
        self._bot = autogen_bot
        self._bot_type = bot_type
        
    async def send_message(self, message: str, **kwargs) -> None:
        await self._bot.send(message, **kwargs)
        
    async def get_response(self) -> str:
        return await self._bot.get_response()
        
    @property
    def capabilities(self) -> Dict[str, Any]:
        base_capabilities = {
            "function_call": True,
            "code_generation": True,
        }
        
        if self._bot_type == "user_proxy":
            base_capabilities.update({
                "code_execution": True,
                "file_operation": True,
            })
            
        return base_capabilities
        
    async def invoke_capability(self, capability_name: str, **kwargs) -> Any:
        if capability_name == "code_execution" and self._bot_type == "user_proxy":
            return await self._bot.execute_code(
                kwargs.get("code"),
                kwargs.get("language", "python"),
                kwargs.get("work_dir", "workspace")
            )
        raise NotImplementedError(f"Capability {capability_name} not supported")