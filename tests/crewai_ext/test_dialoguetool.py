# 测试用例：使用 DialogueTool 根据 Tags 中的 VersionId 查找特定对话
from uuid import UUID
from src.crewai_ext.tools.opera_api.dialogue_api_tool import DialogueTool

opera_id = UUID("99a51bfa-0b95-46e5-96b3-e3cfc021a6b2")

# 创建 DialogueTool 实例
dialogue_tool = DialogueTool()

# 调用 get_filtered 操作查找包含特定 VersionId 的对话
result = dialogue_tool._run(
    action="get_filtered",
    opera_id=opera_id,
    data={
        # 基本过滤条件
        "includes_stage_index_null": True,
        "includes_narratage": True,
        "includes_staff_id_null": True,
        # 标签节点值过滤
        "tag_node_values": [
            {"path": "$.ResourcesForViewing.VersionId", "value": "6a737f18-4d82-496f-8f63-5367e897c583", "type": "String"}
        ],
        "tag_node_values_and_mode": True,  # 确保满足所有条件
    },
)

print(result)
