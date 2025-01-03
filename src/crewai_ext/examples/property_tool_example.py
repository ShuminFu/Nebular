"""Opera属性管理API工具使用示例，展示了如何使用PropertyTool进行属性的获取和更新操作。"""

from crewai import Agent, Task, Crew
from src.crewai_core.tools.opera_api.property_api_tool import PropertyTool
from src.crewai_core.configs.config import llm


# 创建Property管理工具
property_tool = PropertyTool()

# 创建管理Property的Agent
property_manager = Agent(
    role='属性管理员',
    goal='管理和维护Opera的属性',
    backstory="""你是一个专业的Opera属性管理员，负责获取和更新Opera的属性。
    你需要确保所有属性操作都符合规范，并能够正确处理各种情况。
    在使用工具时，请注意：
    1. 所有布尔值都需要使用字符串表示，如"true"或"false"
    2. 不要在字典中使用多余的空格或换行
    3. 所有的值都应该是字符串类型，除非特别说明
    """,
    tools=[property_tool],
    verbose=True,
    llm=llm
)

# 定义任务
tasks = [
    Task(
        description="""获取Opera的所有属性，要求：
        1. src ID为'96028f82-9f76-4372-976c-f0c5a054db79'
        2. 强制从数据库读取（force=true）
        在使用工具时，请注意：
        1. 所有布尔值都需要使用字符串表示，如"true"或"false"
        2. 不要使用多余的空格或换行
        3. 所有的值都应该是字符串类型，除非特别说明
        """,
        expected_output="返回Opera的所有属性列表",
        agent=property_manager
    ),

    Task(
        description="""获取指定的属性值，要求：
        1. src ID为'96028f82-9f76-4372-976c-f0c5a054db79'
        2. 属性键名为'test_key'
        3. 从缓存读取（不设置force）
        在使用工具时，请注意：
        1. 所有布尔值都需要使用字符串表示，如"true"或"false"
        2. 不要使用多余的空格或换行
        3. 所有的值都应该是字符串类型，除非特别说明
        """,
        expected_output="返回指定属性的值，如果属性不存在则返回相应提示",
        agent=property_manager
    ),

    Task(
        description="""更新Opera的属性，要求：
        1. src ID为'96028f82-9f76-4372-976c-f0c5a054db79'
        2. 新增或更新以下属性：
           - test_key: "test_value"
           - example_key: "example_value"
        3. 删除属性：old_key
        在使用工具时，请注意：
        1. 所有布尔值都需要使用字符串表示，如"true"或"false"
        2. 不要使用多余的空格或换行
        3. 所有的值都应该是字符串类型，除非特别说明
        """,
        expected_output="成功更新属性，并返回更新结果",
        agent=property_manager
    ),

    Task(
        description="""验证属性更新结果，要求：
        1. src ID为'96028f82-9f76-4372-976c-f0c5a054db79'
        2. 获取所有属性
        3. 确认新属性已添加且旧属性已删除
        在使用工具时，请注意：
        1. 所有布尔值都需要使用字符串表示，如"true"或"false"
        2. 不要使用多余的空格或换行
        3. 所有的值都应该是字符串类型，除非特别说明
        """,
        expected_output="返回更新后的属性列表，确认更新操作的结果",
        agent=property_manager
    )
]

# 创建和运行Crew
crew = Crew(
    agents=[property_manager],
    tasks=tasks,
    verbose=True
)

# 执行任务
result = crew.kickoff()
print("\n最终结果:", result) 