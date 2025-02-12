import json
from datetime import datetime, timezone, timedelta
from unittest import TestCase
from uuid import UUID

from src.core.dialogue.analyzers import DialogueAnalyzer
from src.core.dialogue.models import ProcessingDialogue, DialogueContext
from src.core.dialogue.pools import DialoguePool
from src.core.dialogue.enums import DialogueType, ProcessingStatus
from src.core.parser.api_response_parser import ApiResponseParser
from src.crewai_ext.tools.opera_api.dialogue_api_tool import _SHARED_DIALOGUE_TOOL


class TestDialogueAnalyzerIntegration(TestCase):
    """对话分析器的集成测试"""

    def setUp(self):
        """测试前的准备工作"""
        self.analyzer = DialogueAnalyzer()

    def test_analyze_context_with_real_data(self):
        """使用真实对话数据的集成测试"""
        # 准备真实对话数据
        opera_id = UUID('96028f82-9f76-4372-976c-f0c5a054db79')
        dialogue_index = 231

        # 使用dialogue api tool获取对话数据
        dialogue_result = _SHARED_DIALOGUE_TOOL.run(
            action="get",
            opera_id=opera_id,
            dialogue_index=dialogue_index
        )
        status_code, dialogue_data = ApiResponseParser.parse_response(dialogue_result)
        self.assertEqual(status_code, 200, "获取对话数据失败")

        # 创建ProcessingDialogue对象
        test_dialogue = ProcessingDialogue(
            dialogue_index=dialogue_data["index"],
            opera_id=opera_id,
            text=dialogue_data["text"],
            type=DialogueType.CODE_RESOURCE,
            status=ProcessingStatus.PENDING,
            context=DialogueContext(
                stage_index=dialogue_data["stageIndex"],
                related_dialogue_indices=[],
                conversation_state={}
            ),
            timestamp=datetime.fromisoformat(dialogue_data["time"].replace('Z', '+00:00')),
            sender_staff_id=UUID(dialogue_data["staffId"]) if dialogue_data.get("staffId") else None,
            is_narratage=dialogue_data.get("isNarratage", False),
            is_whisper=dialogue_data.get("isWhisper", False),
            tags=dialogue_data.get("tags"),
            mentioned_staff_ids=dialogue_data.get("mentionedStaffIds", [])
        )

        # 添加基本验证
        self.assertEqual(test_dialogue.dialogue_index, dialogue_data["index"])
        self.assertEqual(test_dialogue.text, dialogue_data["text"])
        self.assertEqual(test_dialogue.type, DialogueType.CODE_RESOURCE)
        self.assertEqual(test_dialogue.sender_staff_id, UUID(dialogue_data["staffId"]) if dialogue_data.get("staffId") else None)
        self.assertEqual(test_dialogue.is_narratage, dialogue_data.get("isNarratage", False))
        self.assertEqual(test_dialogue.is_whisper, dialogue_data.get("isWhisper", False))
        self.assertEqual(test_dialogue.tags, dialogue_data.get("tags"))
        self.assertEqual(test_dialogue.mentioned_staff_ids, dialogue_data.get("mentionedStaffIds", []))

        # 创建对话池并添加相关对话
        dialogue_pool = DialoguePool()
        dialogue_pool.dialogues = [test_dialogue]

        # 获取前后各5条对话作为上下文
        for offset in range(-6, 0):
            if offset == 0:
                continue
            idx = dialogue_index + offset
            if idx < 0:
                continue

            context_result = _SHARED_DIALOGUE_TOOL.run(
                action="get",
                opera_id=opera_id,
                dialogue_index=idx
            )
            status_code, context_data = ApiResponseParser.parse_response(context_result)
            if status_code == 200 and context_data:
                context_dialogue = ProcessingDialogue(
                    dialogue_index=context_data["index"],
                    opera_id=opera_id,
                    text=context_data["text"],
                    type=DialogueType.CODE_RESOURCE,
                    status=ProcessingStatus.PENDING,
                    context=DialogueContext(
                        stage_index=context_data["stageIndex"],
                        related_dialogue_indices=[],
                        conversation_state={}
                    ),
                    timestamp=datetime.fromisoformat(context_data["time"].replace('Z', '+00:00')),
                    sender_staff_id=UUID(context_data["staffId"]) if context_data.get("staffId") else None,
                    is_narratage=context_data.get("isNarratage", False),
                    is_whisper=context_data.get("isWhisper", False),
                    tags=context_data.get("tags"),
                    mentioned_staff_ids=context_data.get("mentionedStaffIds", [])
                )
                dialogue_pool.dialogues.append(context_dialogue)

        # 执行上下文分析
        result = self.analyzer.analyze_context(test_dialogue, dialogue_pool)

        # 验证结果
        self.assertIsInstance(result, set)
        self.assertGreaterEqual(len(result), 0)

        # 验证conversation_state
        self.assertIn("flow", test_dialogue.context.conversation_state)
        self.assertIn("code_context", test_dialogue.context.conversation_state)
        self.assertIn("decision_points", test_dialogue.context.conversation_state)
        self.assertIn("context_variables", test_dialogue.context.conversation_state)
        self.assertIn("analyzed_at", test_dialogue.context.conversation_state)

        # 打印分析结果以供查看
        print("\n=== 上下文分析结果 ===")
        print(f"当前对话: {test_dialogue.text}")
        print(f"相关对话索引: {result}")
        print(f"对话状态: {json.dumps(test_dialogue.context.conversation_state, indent=2, ensure_ascii=False)}")

        # 打印相关对话内容
        print("\n=== 相关对话内容 ===")
        for dialogue in dialogue_pool.dialogues:
            if dialogue.dialogue_index in result:
                print(f"索引 {dialogue.dialogue_index}: {dialogue.text}")
