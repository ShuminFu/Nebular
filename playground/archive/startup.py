import autogen
from autogen import AssistantAgent, UserProxyAgent

config_list = autogen.config_list_from_json(
    env_or_file="configs/OAI_COMPATIBLE_CFG.json",
)
llm_config = {"config_list": config_list}
assistant = AssistantAgent("assistant", llm_config=llm_config)
user_proxy = UserProxyAgent("user_proxy", code_execution_config=False)

# Start the chat
user_proxy.initiate_chat(
    assistant,
    message="Tell me a joke about NVDA and TESLA stock prices.",
)

assistant.DEFAULT_SYSTEM_MESSAGE
