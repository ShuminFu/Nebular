"""临时文件工具使用示例，展示了如何使用TempFileTool进行临时文件的上传、追加和删除操作。"""
from crewai import Agent, Task, Crew
from ai_core.tools.temp_file_api_tool import TempFileTool
from ai_core.configs.config import llm


# 创建临时文件管理工具
temp_file_tool = TempFileTool()

# 创建管理临时文件的Agent
temp_file_manager = Agent(
    role='临时文件管理员',
    goal='管理系统中的临时文件',
    backstory="""你是一个专业的临时文件管理员，负责文件的上传、追加和删除操作。
    你需要确保所有文件操作都符合规范，并能够正确处理二进制数据。
    在处理临时文件时，请注意：
    1. 文件数据必须是有效的二进制格式
    2. 临时文件ID必须是有效的UUID
    3. 追加操作前确保文件存在
    4. 及时清理不需要的临时文件
    """,
    tools=[temp_file_tool],
    verbose=True,
    llm=llm
)

# 测试用的示例数据
SAMPLE_DATA = b"Hello, this is a test file content!"
SAMPLE_DATA_2 = b" This is additional content."

# 定义任务
tasks = [
    Task(
        description="""上传一个新的临时文件，要求：
        1. 生成一段随机的SAMPLE DATA作为文件内容
        2. 不指定临时文件ID（创建新文件）""",
        expected_output="成功上传临时文件，并返回文件ID和长度信息",
        agent=temp_file_manager
    ),

    Task(
        description="""追加数据到刚才创建的临时文件，要求：
        1. 使用上一个任务返回的文件ID
        2. 生成另一段随机的SAMPLE DATA作为追加内容""",
        expected_output="成功追加数据，并返回更新后的文件长度",
        agent=temp_file_manager
    ),

    Task(
        description="""上传新文件并指定ID，要求：
        1. 使用上一个任务中的文件ID
        2. 使用新的SAMPLE DATA作为内容
        3. 验证文件长度是否正确更新""",
        expected_output="成功上传并追加到指定ID的文件，返回更新后的长度信息",
        agent=temp_file_manager
    ),

    # Task(
    #     description="""删除临时文件，要求：
    #     1. 使用上一个任务中的文件ID
    #     2. 确认删除是否成功""",
    #     expected_output="成功删除临时文件",
    #     agent=temp_file_manager
    # ),

    # Task(
    #     description="""验证文件删除，要求：
    #     1. 尝试追加数据到已删除的文件
    #     2. 确认操作失败并返回404错误""",
    #     expected_output="操作失败，返回文件不存在的错误",
    #     agent=temp_file_manager
    # )
]

# 创建和运行Crew
crew = Crew(
    agents=[temp_file_manager],
    tasks=tasks,
    verbose=True
)

# 执行任务
result = crew.kickoff()
print("\n最终结果:", result) 