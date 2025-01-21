"""Resource API工具使用示例，展示了如何使用ResourceApiTool进行资源的创建、查询、更新等操作。"""
from uuid import UUID
from crewai import Agent, Task, Crew
from src.crewai_ext.tools.opera_api.resource_api_tool import ResourceTool
from src.crewai_ext.config.llm_setup import llm


# 创建Resource管理工具
resource_tool = ResourceTool()

# 创建管理Resource的Agent
resource_manager = Agent(
    role='资源管理员',
    goal='管理和维护系统中的资源文件',
    backstory="""你是一个专业的资源管理员，负责创建、更新、查询和删除资源文件。
    你需要确保所有资源操作都符合规范，并能够正确处理各种MIME类型的文件。
    在处理资源时，请注意：
    1. 确保提供正确的MIME类型
    2. 资源名称应该具有描述性
    3. 所有的UUID都应该是有效的
    4. 临时文件ID必须在创建资源前准备好
    """,
    tools=[resource_tool],
    verbose=True,
    llm=llm
)

# 测试用的Opera ID和临时文件ID
OPERA_ID = UUID("96028f82-9f76-4372-976c-f0c5a054db79")
TEMP_FILE_ID = UUID("60aba5b4-e7cd-415e-bf0f-56d3d9d35774")

# 定义任务
tasks = [
    # Task(
    #     description=f"""创建一个新的资源文件，要求：
    #     1. src ID为'{OPERA_ID}'
    #     2. 临时文件ID为'{TEMP_FILE_ID}'
    #     3. 名称为'测试文档.txt'
    #     4. 描述为即兴发挥生成，但是要表明是resource tool生成的。
    #     5. MIME类型为'text/plain'
    #     6. lastUpdateStaffName为'resource tool'""",
    #     expected_output="成功创建资源文件，并返回资源的详细信息",
    #     agent=resource_manager
    # ),

    # Task(
    #     description=f"""获取所有资源文件列表，src ID为'{OPERA_ID}'""",
    #     expected_output="返回系统中所有资源文件的列表，确认其中包含刚刚创建的资源",
    #     agent=resource_manager
    # ),

    Task(
        description=f"""按条件过滤资源文件，要求：
        1. Opera ID为'{OPERA_ID}'
        2. 名称为'manualupdate'
        3. MIME类型为'text/plain'""",
        expected_output="返回符合条件的资源文件列表",
        agent=resource_manager
    ),

    Task(
        description="""更新指定资源文件的信息：
        1. 使用上一个任务中找到的资源ID
        2. 更新描述为'这是一个更新后的测试文本文件'
        3. 更新最后更新者名称为'更新测试人员'""",
        expected_output="成功更新资源文件信息，并返回更新后的详细信息",
        agent=resource_manager
    ),

    Task(
        description="""下载资源文件：
        1. 使用上一个任务中的资源ID
        2. 下载文件内容""",
        expected_output="成功下载资源文件内容",
        agent=resource_manager
    ),

    Task(
        description="""删除资源文件：
        1. 使用上一个任务中的资源ID
        2. 确认删除操作""",
        expected_output="成功删除资源文件",
        agent=resource_manager
    )
]

# 创建和运行Crew
crew = Crew(
    agents=[resource_manager],
    tasks=tasks,
    verbose=True
)

# 执行任务
result = crew.kickoff()
print("\n最终结果:", result)
