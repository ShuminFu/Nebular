"""测试DialogueTool的直接运行功能"""

from src.crewai_ext.tools.opera_api.dialogue_api_tool import DialogueTool
from src.opera_service.api.models import DialogueForCreation, DialogueForFilter
from uuid import UUID


def test_dialogue_tool_direct_run():
    """直接测试DialogueTool的_run方法，不通过CrewAI的工具调用机制"""

    # 初始化工具
    dialogue_tool = DialogueTool()

    # 生成测试用的UUID
    test_opera_id = UUID("99a51bfa-0b95-46e5-96b3-e3cfc021a6b2")
    test_staff_id = UUID("99a51bfa-0b95-46e5-96b3-e3cfc021a6b2")

    # 1. 测试获取所有对话
    print("\n=== 测试获取所有对话 ===")
    get_all_result = dialogue_tool._run(action="get_all", opera_id=test_opera_id)
    print(get_all_result)

    # 2. 测试获取单个对话
    print("\n=== 测试获取单个对话 ===")
    get_result = dialogue_tool._run(action="get", opera_id=test_opera_id, dialogue_index=1)
    print(get_result)

    # 3. 测试创建对话
    print("\n=== 测试创建对话 ===")
    # # 创建DialogueForCreation实例
    # dialogue_data = DialogueForCreation(
    #     is_stage_index_null=False,
    #     staff_id=test_staff_id,
    #     is_narratage=False,
    #     is_whisper=False,
    #     text="这是一条测试对话",
    #     tags="测试,对话",
    # )

    # create_result = dialogue_tool._run(action="create", opera_id=test_opera_id, data=dialogue_data)
    # print(create_result)
    print("skipped")

    # 4. 测试条件过滤查询对话
    print("\n=== 测试条件过滤查询对话 ===")
    filter_data = DialogueForFilter(
        index_not_before=1,
        index_not_after=10,
        top_limit=100,
        stage_index=1,
        includes_stage_index_null=True,
        includes_narratage=True,
        includes_for_staff_id_only=test_staff_id,
        includes_staff_id_null=True,
    )

    filter_result = dialogue_tool._run(action="get_filtered", opera_id=test_opera_id, data=filter_data)
    print(filter_result)

    # 5. 测试获取最新对话索引
    print("\n=== 测试获取最新对话索引 ===")
    latest_index_result = dialogue_tool._run(action="get_latest_index", opera_id=test_opera_id)
    print(latest_index_result)


if __name__ == "__main__":
    test_dialogue_tool_direct_run()
