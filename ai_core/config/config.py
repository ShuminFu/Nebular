from crewai import LLM, Agent, Crew, Task
from crewai_tools.tools.serper_dev_tool.serper_dev_tool import SerperDevTool
from dotenv import load_dotenv

from tools.bot_api_tool import BotTool

load_dotenv(".env")
import os
llm = LLM(
    model="azure/gpt-4o",
    api_key=os.environ.get("AZURE_API_KEY"),
    base_url=os.environ.get("AZURE_API_BASE")
)

INIT_CREW_MANAGER = {
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
INIT_CREW_MANAGER_TASK ={
    "description": """
    作为Bot管理员，你需要视任务情况进行以下工作：
    1. 管理Bot生命周期：创建、更新、查询和删除Bot
    2. 处理Opera Staff邀请：根据需求向指定Bot发送邀请
    3. 监控Bot状态：确保Bot正常运行并记录异常情况
    4. 维护Bot配置：确保配置信息准确且最新
    5. 执行权限控制：管理Bot的访问权限和操作限制
    """,
    "expected_output": "根据任务返回对应的信息，比如创建Bot得到的响应详情或者发送邀请得到的响应详情",
}

TEMPLATE_USAGE=Agent(
    tools=[BotTool()],
    llm=llm,
    **INIT_CREW_MANAGER
)