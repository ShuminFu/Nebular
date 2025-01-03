"""Stage API工具使用示例，展示了如何使用StageTool进行场幕的创建和查询等操作。"""

from crewai import Agent, Task, Crew
from src.crewai_ext.tools.opera_api.stage_api_tool import StageTool
from src.crewai_ext.configs.config import llm


# 创建Stage管理工具
stage_tool = StageTool()

# 创建管理Stage的Agent
stage_manager = Agent(
    role='Stage管理员',
    goal='管理和维护系统中的场幕',
    backstory="""你是一个专业的场幕管理员，负责创建和查询场幕。
    你需要确保所有场幕的操作都符合规范，并能够正确处理各种情况。
    在使用工具时，请注意：
    1. 所有布尔值都需要使用字符串表示，如"true"或"false"
    2. 不要在字典中使用多余的空格或换行
    3. 所有的值都应该是字符串类型，除非特别说明
    """,
    tools=[stage_tool],
    verbose=True,
    llm=llm
)

# 定义任务
tasks = [
    Task(
        description="""创建一个新的场幕，要求：
        1. src ID为'96028f82-9f76-4372-976c-f0c5a054db79'
        2. 名称为'第一幕：序章'""",
        expected_output="成功创建场幕，并返回场幕的详细信息",
        agent=stage_manager
    ),

    Task(
        description="""获取所有场幕列表，src ID为'96028f82-9f76-4372-976c-f0c5a054db79'""",
        expected_output="返回系统中所有场幕的列表，确认其中有刚刚创建的场幕",
        agent=stage_manager
    ),

    Task(
        description="""获取当前场幕，要求：
        1. src ID为'96028f82-9f76-4372-976c-f0c5a054db79'
        2. 强制从数据库读取（force=true）""",
        expected_output="返回当前场幕的信息",
        agent=stage_manager
    ),

    Task(
        description="""获取指定索引的场幕：
        1. src ID为'96028f82-9f76-4372-976c-f0c5a054db79'
        2. 场幕索引为0""",
        expected_output="返回指定索引场幕的详细信息",
        agent=stage_manager
    )
]

# 创建和运行Crew
crew = Crew(
    agents=[stage_manager],
    tasks=tasks,
    verbose=True
)

# 执行任务
result = crew.kickoff()
print("\n最终结果:", result) 