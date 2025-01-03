"""Dialogue API工具使用示例，展示了如何使用DialogueTool进行对话的创建和查询等操作。"""

from crewai import Agent, Task, Crew
from src.crewai_ext.tools.opera_api.dialogue_api_tool import DialogueTool
from src.crewai_ext.configs.config import llm


# 创建Dialogue管理工具
dialogue_tool = DialogueTool()

# 创建管理Dialogue的Agent
dialogue_manager = Agent(
    role='对话管理员',
    goal='管理和维护系统中的对话',
    backstory="""你是一个专业的对话管理员，负责创建, 过滤和查询对话。
    你需要确保所有对话操作都符合规范，并能够正确处理各种情况。
    在使用工具时，请注意：
    1. 所有布尔值都需要使用字符串表示，如"true"或"false"
    2. 不要使用多余的空格或换行
    3. 所有的值都应该是字符串类型，除非特别说明
    """,
    tools=[dialogue_tool],
    verbose=True,
    llm=llm
)

# 定义任务
tasks = [
    # Task(
    #     description="""创建一个新的对话，要求：
    #     1. src ID为'96028f82-9f76-4372-976c-f0c5a054db79'
    #     2. Staff ID为'ab01d4f7-bbf1-44aa-a55b-cbc7d62fbfbc'
    #     3. 不是旁白（is_narratage为false）
    #     4. 不是悄悄话（is_whisper为false）
    #     5. 有场景索引（is_stage_index_null为false）
    #     6. 对话内容为即兴发挥生成，但是要表明是dialogue tool生成的。
    #     7. 标签为'test,demo'
    #     8. 提到的Staff IDs为['c2a71833-4403-4d08-8ef6-23e6327832b2']""",
    #     expected_output="成功创建对话，并返回对话的详细信息",
    #     agent=dialogue_manager
    # ),

    Task(
        description="""获取最新对话的索引值，src ID为'96028f82-9f76-4372-976c-f0c5a054db79'""",
        expected_output="返回最新对话的索引值，如果没有对话则返回0",
        agent=dialogue_manager
    ),

    # Task(
    #     description="""获取所有对话列表，src ID为'96028f82-9f76-4372-976c-f0c5a054db79'""",
    #     expected_output="返回系统中所有对话的列表，确认其中有刚刚创建的对话",
    #     agent=dialogue_manager
    # ),

    # Task(
    #     description="""按条件过滤查询对话，要求：
    #     1. src ID为'96028f82-9f76-4372-976c-f0c5a054db79'
    #     2. 索引范围：1-20
    #     3. 返回记录数上限：100
    #     4. 包含场景索引为1的对话
    #     5. 包含无场景索引的对话（includes_stage_index_null为true）
    #     6. 包含旁白（includes_narratage为true）
    #     7. 只包含指定Staff的对话（includes_for_staff_id_only为'7c80efe6-a18a-43f5-8bc8-853a29d78bd7'）
    #     8. 包含无Staff的对话（includes_staff_id_null为true）""",
    #     expected_output="返回符合条件的对话列表",
    #     agent=dialogue_manager
    # ),

    # Task(
    #     description="""获取指定索引的对话：
    #     1. src ID为'96028f82-9f76-4372-976c-f0c5a054db79'
    #     2. 对话索引为1""",
    #     expected_output="返回指定索引对话的详细信息",
    #     agent=dialogue_manager
    # )
]

# 创建和运行Crew
crew = Crew(
    agents=[dialogue_manager],
    tasks=tasks,
    verbose=True
)

# 执行任务
result = crew.kickoff()
print("\n最终结果:", result) 