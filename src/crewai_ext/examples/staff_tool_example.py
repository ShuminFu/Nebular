"""Staff API工具使用示例，展示了如何使用StaffTool进行Staff的创建、查询、更新等操作。"""

from crewai import Agent, Task, Crew
from src.crewai_core.tools.opera_api.staff_api_tool import StaffTool
from src.crewai_core.configs.config import llm


# 创建Staff管理工具
staff_tool = StaffTool()

# 创建管理Staff的Agent
staff_manager = Agent(
    role='Staff管理员',
    goal='管理和维护系统中的Staff',
    backstory="""你是一个专业的Staff管理员，负责创建、更新、查询和删除Staff。
    你需要确保所有Staff的操作都符合规范，并能够正确处理各种情况。
    在使用工具时，请注意：
    1. 所有布尔值都需要使用字符串表示，如"true"或"false"
    2. 不要字典中使用多余的空格或换行
    3. 所有的值都应该是字符串类型，除非特别说明
    """,
    tools=[staff_tool],
    verbose=True,
    llm=llm
)

# 定义任务
tasks = [
    Task(
        description="""创建一个新的Staff，要求：
        1. src ID为'96028f82-9f76-4372-976c-f0c5a054db79'
        2. Bot ID为'7c80efe6-a18a-43f5-8bc8-853a29d78bd7'
        3. 名称为'TestStaff-staff-tool-example'
        4. 参数为'{"role": "tester"}'
        5. 设置为在台上（is_on_stage为true）
        6. 标签为'test,demo'
        7. 角色为'tester'
        8. 权限为'basic'""",
        expected_output="成功创建Staff，并返回Staff的详细信息",
        agent=staff_manager
    ),

    Task(
        description="""获取所有Staff列表，src ID为'96028f82-9f76-4372-976c-f0c5a054db79'""",
        expected_output="返回系统中所有Staff的列表, 确认其中有刚刚创建的Staff",
        agent=staff_manager
    ),

    Task(
        description="""按名称模糊查询Staff，要求：
        1. src ID为'96028f82-9f76-4372-976c-f0c5a054db79'
        2. 名称包含'Test'
        3. 只查询在台上的Staff""",
        expected_output="返回符合条件的Staff列表",
        agent=staff_manager
    ),

    Task(
        description="""更新指定Staff的信息：
        1. src ID为'96028f82-9f76-4372-976c-f0c5a054db79'
        2. Staff ID为 刚刚创建的名为TestStaff-staff-tool-example
        3. 更新参数为'{"role": "senior_tester"}'
        4. 更新在台状态为false""",
        expected_output="成功更新Staff信息，并返回更新后的详细信息",
        agent=staff_manager
    )
]

# 创建和运行Crew
crew = Crew(
    agents=[staff_manager],
    tasks=tasks,
    verbose=True
)

# 执行任务
result = crew.kickoff()
print("\n最终结果:", result)
