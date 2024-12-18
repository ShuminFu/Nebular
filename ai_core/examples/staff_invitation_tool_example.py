"""Staff邀请API工具使用示例，展示了如何使用StaffInvitationTool进行Staff邀请的创建、查询、删除和接受等操作。"""

from crewai import Agent, Task, Crew
from ai_core.tools.opera_api.staff_invitation_api_tool import StaffInvitationTool
from ai_core.configs.config import llm


# 创建Staff邀请管理工具
staff_invitation_tool = StaffInvitationTool()

# 创建管理Staff邀请的Agent
invitation_manager = Agent(
    role='Staff邀请管理员',
    goal='管理和维护系统中的Staff邀请',
    backstory="""你是一个专业的Staff邀请管理员，负责创建、查询、删除和接受Staff邀请。
    你需要确保所有邀请操作都符合规范，并能够正确处理各种情况。
    在使用工具时，请注意：
    1. 所有布尔值都需要使用字符串表示，如"true"或"false"
    2. 不要在字典中使用多余的空格或换行
    3. 所有的值都应该是字符串类型，除非特别说明
    """,
    tools=[staff_invitation_tool],
    verbose=True,
    llm=llm
)

# 定义任务
tasks = [
    Task(
        description="""创建一个新的Staff邀请，要求：
        1. Opera ID为'96028f82-9f76-4372-976c-f0c5a054db79'
        2. Bot ID为'ff94e0b6-9212-497e-8f7d-456242a88668'
        3. 参数为'{"role": "invited_tester"}'
        4. 标签为'test,invited'
        5. 角色为'tester'
        6. 权限为'basic'""",
        expected_output="成功创建Staff邀请，并返回邀请的详细信息",
        agent=invitation_manager
    ),

    Task(
        description="""获取所有Staff邀请列表，Opera ID为'96028f82-9f76-4372-976c-f0c5a054db79'""",
        expected_output="返回系统中所有Staff邀请的列表，确认其中有刚刚创建的邀请, 并返回邀请ID",
        agent=invitation_manager
    ),

    Task(
        description="""获取指定的Staff邀请详情：
        1. Opera ID为'96028f82-9f76-4372-976c-f0c5a054db79'
        2. 使用上一步获取到的邀请ID""",
        expected_output="返回指定Staff邀请的详细信息",
        agent=invitation_manager
    ),

    Task(
        description="""接受Staff邀请：
        1. Opera ID为'96028f82-9f76-4372-976c-f0c5a054db79'
        2. 使用上一步的邀请ID
        3. 名称为'TestStaff-Invited'
        4. 设置为在台上（is_on_stage为true）
        5. 使用邀请中的参数、标签、角色和权限""",
        expected_output="成功接受Staff邀请，并返回创建的Staff ID",
        agent=invitation_manager
    ),

    Task(
        description="""删除已接受的Staff邀请：
        1. Opera ID为'96028f82-9f76-4372-976c-f0c5a054db79'
        2. 使用上述邀请ID""",
        expected_output="成功删除Staff邀请",
        agent=invitation_manager
    )
]

# 创建和运行Crew
crew = Crew(
    agents=[invitation_manager],
    tasks=tasks,
    verbose=True
)

# 执行任务
result = crew.kickoff()
print("\n最终结果:", result) 