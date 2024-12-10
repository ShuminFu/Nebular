import os
from crewai import LLM, Agent, Crew, Task

from dotenv import load_dotenv
from pathlib import Path

from ai_core.tools.bot_api_tool import BotTool

env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

llm = LLM(
    model="azure/gpt-4o",
    api_key=os.environ.get("AZURE_API_KEY"),
    base_url=os.environ.get("AZURE_API_BASE")
)
# llm = LLM(
#     model="gpt-4o",
#     api_key=os.environ.get("OPENAI_API_KEY"),
#     base_url=os.environ.get("http://10.1.11.55:3000/v1")
# )

DEFAULT_CREW_MANAGER_PROMPT = {
    "role": "Bot管理员, Staff邀请发送者",
    "goal": "管理和维护系统中的Bot, 在需要的时候发送Opera邀请给正确的Bot",
    "backstory": """你是一个专业的Bot管理员，负责创建、更新、查询和删除Bot。同时你根据负责根据Opera给Bot发送对应的Staff邀请。
    你需要确保所有Bot的操作都符合规范，并能够正确处理各种情况。
    无论如何，所有true, false都请你使用字符串表示或者使用双引号包括起来，比如"True","False"
    """,
    "memory": False,
    "verbose": True,
    "allow_delegation": True,
    "max_iter": 20,
    "max_retry_limit": 3,
    "allow_code_execution": True,
    "respect_context_window": True,
    "use_system_prompt": True
}
# ps: can be modified later by Task()[0].description
CREW_MANAGER_INIT = {
    "description": """
    查询所有Bot列表中名为BotManager的Bot
    """,
    "expected_output": "返回不在活跃状态的Bot ID列表以及详情",
} # 怎么感觉这个也可以coding实现

# GET_SUB_BOTS_BY_TAG = {
#     "description":"""
#     根据这个Bot的TAG 分析出所有的子Bot的ID
#     """,
#     "expected_output":"返回所有子Bot的ID列表"
# } # 这个可以直接通过coding调用API工具实现，而不用通过AI来调用API工具



DEFAULT_CREW_MANAGER = Agent(
    tools=[BotTool()],
    llm=llm,
    **DEFAULT_CREW_MANAGER_PROMPT
)
if __name__ == "__main__":
    crew = Crew(
        agents=[DEFAULT_CREW_MANAGER],
        tasks=[Task(**CREW_MANAGER_INIT)]
    )
    crew.kickoff()
