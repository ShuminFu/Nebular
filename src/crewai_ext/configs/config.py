import os
from crewai import LLM, Agent, Crew, Task

from dotenv import load_dotenv
from pathlib import Path

from src.crewai_ext.tools.opera_api.bot_api_tool import BotTool

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

test_config = {
    'agents': [
        {
            'name': '前端架构专家',
                    'role': '资深前端工程师',
                    'goal': '设计和实现高质量的前端代码，确保代码的可维护性和性能',
                    'backstory': '''你是一个经验丰富的前端架构师，擅长：
                    1. 响应式布局设计和实现
                    2. 组件化开发和模块化设计
                    3. 性能优化和最佳实践
                    4. 主流前端框架和工具的使用
                    5. 代码质量和架构设计
                    
                    你需要：
                    1. 理解整个项目的结构和依赖关系
                    2. 确保生成的代码符合现代前端开发标准
                    3. 正确处理文件间的引用关系
                    4. 实现响应式和交互功能
                    5. 遵循代码最佳实践''',
                    'tools': []
        },
        {
            'name': 'UI交互专家',
                    'role': 'UI/UX工程师',
                    'goal': '实现流畅的用户交互和优秀的用户体验',
                    'backstory': '''你是一个专注于用户体验的UI工程师，擅长：
                    1. 交互设计和实现
                    2. 动画效果开发
                    3. 用户体验优化
                    4. 无障碍设计
                    5. 响应式UI组件开发
                    
                    你需要：
                    1. 设计流畅的交互体验
                    2. 实现符合直觉的用户界面
                    3. 确保跨设备的一致性
                    4. 优化加载和响应速度
                    5. 处理各种边界情况''',
                    'tools': []
        }
    ],
    'process': 'sequential',  # 使用协作模式，决定是否让多个专家共同完成任务
    'verbose': True
}

if __name__ == "__main__":
    crew = Crew(
        agents=[DEFAULT_CREW_MANAGER],
        tasks=[Task(**CREW_MANAGER_INIT)]
    )
    crew.kickoff()
