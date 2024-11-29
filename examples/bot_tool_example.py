from crewai import Agent, Task, Crew,LLM
from latest_ai_development.tools.bot_api_tool import BotTool

llm_oneapi = LLM(
    model="gpt-4o",
    api_key="sk-LiZdw3jCJJ4UYver9e86625c0c6043B69820DfE3B99bA736",
    base_url="http://10.1.11.55:3000/v1"
)
# 创建Bot管理工具
bot_tool = BotTool()

# 创建管理Bot的Agent
bot_manager = Agent(
    role='Bot管理员',
    goal='管理和维护系统中的Bot',
    backstory="""你是一个专业的Bot管理员，负责创建、更新、查询和删除Bot。
    你需要确保所有Bot的操作都符合规范，并能够正确处理各种情况。
    无论如何，所有true, false都请你使用字符串表示或者使用双引号包括起来，比如"True","False"
    """,
    tools=[bot_tool],
    verbose=True,
    llm=llm_oneapi
)

# 定义任务
tasks = [
    # Task(
    #     description="""创建一个新的Bot，要求：
    #     1. 名称为 'TestBot'
    #     2. 描述为 '这是一个测试用Bot'
    #     3. 设置默认标签为 'test,demo'
    #     4. 设置默认角色为 'tester'""",
    #     expected_output="成功创建Bot，并返回Bot的详细信息",
    #     agent=bot_manager
    # ),
    #
    # Task(
    #     description="获取所有Bot的列表",
    #     expected_output="返回系统中所有Bot的列表",
    #     agent=bot_manager
    # ),

    # Task(
    #     description="获取Bot'e822fd9b-a360-4eb7-b217-c4f86f2dcee6'的信息",
    #     expected_output="返回该Bot的信息",
    #     agent=bot_manager
    # ),

    Task(
        description="""基于上一个创建任务返回的Bot ID，或者是'e822fd9b-a360-4eb7-b217-c4f86f2dcee6'。更新该Bot的信息：
        1. 更新描述为 '这是更新后的测试Bot'
        2. 更新默认标签为 'updated,test',
        3. 所有true, false都请你使用字符串表示或者使用双引号包括起来，比如"True","False"
        """,
        expected_output="成功更新Bot信息，并返回更新后的详细信息",
        agent=bot_manager
    )
]

# 创建和运行Crew
crew = Crew(
    agents=[bot_manager],
    tasks=tasks,
    verbose=True
)

# 执行任务
result = crew.kickoff()
print("\n最终结果:", result)