from crewai import Agent, Task, Crew, LLM
from ai_core.tools.opera_api_tool import OperaTool

llm_oneapi = LLM(
    model="gpt-4o",
    api_key="sk-LiZdw3jCJJ4UYver9e86625c0c6043B69820DfE3B99bA736",
    base_url="http://10.1.11.55:3000/v1"
)

# 创建Opera管理工具
opera_tool = OperaTool()

# 创建管理Opera的Agent
opera_manager = Agent(
    role='Opera管理员',
    goal='管理和维护系统中的Opera',
    backstory="""你是一个专业的Opera管理员，负责创建、更新、查询和删除Opera。
    你需要确保所有Opera的操作都符合规范，并能够正确处理各种情况。
    无论如何，所有true, false都请你使用字符串表示或者使用双引号包括起来，比如"True","False"。
    在创建和更新Opera时，要特别注意数据的格式和必填字段的要求。
    """,
    tools=[opera_tool],
    verbose=True,
    llm=llm_oneapi
)

# 定义任务
tasks = [
    Task(
        description="""创建一个新的Opera，要求：
        1. 名称为 'TestOpera'
        2. 描述为 '这是一个测试用Opera'
        3. 不设置父Opera（作为根节点）
        4. 使用一个狂拽酷炫的数据库名
        """,
        expected_output="成功创建Opera，并返回Opera的详细信息",
        agent=opera_manager
    ),

    Task(
        description="获取所有根节点Opera的列表",
        expected_output="返回系统中所有根节点Opera的列表",
        agent=opera_manager
    ),

    Task(
        description="""基于第一个创建任务返回的Opera ID，更新该Opera的信息：
        1. 更新名称为 'UpdatedTestOpera'
        2. 更新描述为 '这是更新后的测试Opera'
        3. 记住所有布尔值都要用字符串形式，如"True"/"False"
        """,
        expected_output="成功更新Opera信息",
        agent=opera_manager
    ),

    Task(
        description="""获取特定Opera的信息：
        1. 使用第一个任务创建的Opera ID
        2. 如果没有具体ID，可以使用一个示例ID：'c2c74b9b-b37d-47c1-9502-aaa490eca794'
        """,
        expected_output="返回指定Opera的详细信息",
        agent=opera_manager
    ),

    # Task(
    #     description="""删除之前创建的Opera：
    #     1. 使用第一个任务创建的Opera ID
    #     2. 如果没有具体ID，可以使用一个示例ID：'c2c74b9b-b37d-47c1-9502-aaa490eca794'
    #     """,
    #     expected_output="成功删除指定的Opera",
    #     agent=opera_manager
    # )
]

# 创建和运行Crew
crew = Crew(
    agents=[opera_manager],
    tasks=tasks,
    verbose=True
)

# 执行任务
result = crew.kickoff()
print("\n最终结果:", result)
