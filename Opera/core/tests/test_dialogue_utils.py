import unittest
from uuid import UUID
from datetime import datetime, timezone, timedelta
import json
import asyncio

from Opera.core.dialogue.pools import DialoguePool
from Opera.core.dialogue.models import DialogueContext, IntentAnalysis, ProcessingDialogue, PersistentDialogueState
from Opera.core.dialogue.enums import DialoguePriority, DialogueType, ProcessingStatus
from ai_core.tools.opera_api.staff_api_tool import _SHARED_STAFF_TOOL
from Opera.core.api_response_parser import ApiResponseParser


class TestProcessingDialogue(unittest.TestCase):
    def setUp(self):
        # 创建测试用的对话实例
        self.test_opera_id = UUID('96028f82-9f76-4372-976c-f0c5a054db79')
        self.test_dialogue = ProcessingDialogue(
            dialogue_index=1,
            opera_id=self.test_opera_id,
            type=DialogueType.NORMAL
        )

    def test_fetch_text_from_api(self):
        # 直接测试实际API调用
        text = self.test_dialogue.text
        self.assertIsInstance(text, str)
        self.assertTrue(len(text) > 0)

    def test_fetch_text_with_invalid_opera_id(self):
        # 测试使用无效的opera_id
        invalid_dialogue = ProcessingDialogue(
            dialogue_index=1,
            opera_id=UUID('91028f82-9f76-4372-976c-f0c5a054db79'),
            type=DialogueType.NORMAL
        )
        text = invalid_dialogue.text
        self.assertEqual(text, "")

    def test_fetch_text_with_invalid_index(self):
        # 测试使用无效的对话索引
        invalid_dialogue = ProcessingDialogue(
            dialogue_index=-1,
            opera_id=self.test_opera_id,
            type=DialogueType.NORMAL
        )
        text = invalid_dialogue.text
        self.assertEqual(text, "")


class AsyncTestCase(unittest.TestCase):
    """支持异步测试的基类"""
    def run_async(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)


class TestDialoguePool(AsyncTestCase):
    async def async_setUp(self):
        """异步设置，创建测试所需的Staff"""
        # 确保测试Staff存在
        for staff_id in [self.test_staff_id1, self.test_staff_id2]:
            # 尝试获取Staff
            result = _SHARED_STAFF_TOOL.run(
                action="get",
                opera_id=self.test_opera_id,
                staff_id=staff_id
            )
            status_code, _ = ApiResponseParser.parse_response(result)

    def setUp(self):
        """设置测试环境"""
        # 使用已知存在的Opera和Staff ID
        self.test_opera_id = UUID('96028f82-9f76-4372-976c-f0c5a054db79')
        self.test_staff_id1 = UUID('c2a71833-4403-4d08-8ef6-23e6327832b2')
        self.test_staff_id2 = UUID('06ec00fc-9546-40b0-b180-b482ba0e0e27')

        # 创建测试用的对话池
        self.pool = DialoguePool()

        # 创建测试用的对话
        self.dialogue1 = ProcessingDialogue(
            dialogue_index=1,
            opera_id=self.test_opera_id,
            type=DialogueType.NORMAL,
            priority=DialoguePriority.NORMAL,
            status=ProcessingStatus.COMPLETED,
            receiver_staff_ids=[self.test_staff_id1],
            created_at=datetime.now(timezone(timedelta(hours=8))),
            text_content="Test dialogue 1"
        )

        self.dialogue2 = ProcessingDialogue(
            dialogue_index=2,
            opera_id=self.test_opera_id,
            type=DialogueType.WHISPER,
            priority=DialoguePriority.HIGH,
            status=ProcessingStatus.PENDING,
            receiver_staff_ids=[self.test_staff_id1, self.test_staff_id2],
            created_at=datetime.now(timezone(timedelta(hours=8))),
            text_content="Test dialogue 2"
        )

        # 添加对话到对话池
        self.pool.dialogues = [self.dialogue1, self.dialogue2]

        # 运行异步设置
        self.run_async(self.async_setUp())

    def test_persist_to_api_success(self):
        """测试成功持久化对话状态到API"""
        self.run_async(self._test_persist_to_api_success())

    async def _test_persist_to_api_success(self):
        # 执行持久化
        await self.pool._persist_to_api()

        # 验证第一个staff的更新
        result = _SHARED_STAFF_TOOL.run(
            action="get",
            opera_id=self.test_opera_id,
            staff_id=self.test_staff_id1
        )
        status_code, staff_data = ApiResponseParser.parse_response(result)
        self.assertEqual(status_code, 200)

        # 验证参数中包含对话状态
        parameters = json.loads(staff_data.get("parameter", "{}"))
        self.assertIn("dialogueStates", parameters)
        dialogue_states = parameters["dialogueStates"]
        self.assertEqual(len(dialogue_states), 2)  # staff1有两个对话

        # 验证第二个staff的更新
        result = _SHARED_STAFF_TOOL.run(
            action="get",
            opera_id=self.test_opera_id,
            staff_id=self.test_staff_id2
        )
        status_code, staff_data = ApiResponseParser.parse_response(result)
        self.assertEqual(status_code, 200)

        # 验证参数中包含对话状态
        parameters = json.loads(staff_data.get("parameter", "{}"))
        self.assertIn("dialogueStates", parameters)
        dialogue_states = parameters["dialogueStates"]
        self.assertEqual(len(dialogue_states), 1)  # staff2只有一个对话

    def test_persist_to_api_with_invalid_staff(self):
        """测试包含无效Staff ID的情况"""
        self.run_async(self._test_persist_to_api_with_invalid_staff())

    async def _test_persist_to_api_with_invalid_staff(self):
        # 添加一个包含无效Staff ID的对话
        invalid_staff_id = UUID('99999999-9999-9999-9999-999999999999')
        self.dialogue1.receiver_staff_ids.append(invalid_staff_id)

        # 执行持久化
        await self.pool._persist_to_api()

        # 验证有效Staff的更新是否成功
        result = _SHARED_STAFF_TOOL.run(
            action="get",
            opera_id=self.test_opera_id,
            staff_id=self.test_staff_id1
        )
        status_code, staff_data = ApiResponseParser.parse_response(result)
        self.assertEqual(status_code, 200)

        # 验证参数中包含对话状态
        parameters = json.loads(staff_data.get("parameter", "{}"))
        self.assertIn("dialogueStates", parameters)

    def test_persist_empty_pool(self):
        """测试持久化空对话池的情况"""
        self.run_async(self._test_persist_empty_pool())

    async def _test_persist_empty_pool(self):
        # 创建空对话池
        empty_pool = DialoguePool()

        # 执行持久化
        await empty_pool._persist_to_api()

        # 验证Staff的状态没有被改变
        for staff_id in [self.test_staff_id1, self.test_staff_id2]:
            result = _SHARED_STAFF_TOOL.run(
                action="get",
                opera_id=self.test_opera_id,
                staff_id=staff_id
            )
            status_code, staff_data = ApiResponseParser.parse_response(result)
            self.assertEqual(status_code, 200)

            # 验证参数没有被修改
            parameters = json.loads(staff_data.get("parameter", "{}"))
            if "dialogueStates" in parameters:
                self.assertEqual(len(parameters["dialogueStates"]), 0)

    def tearDown(self):
        """清理测试环境"""
        self.run_async(self._tearDown())

    async def _tearDown(self):
        """异步清理测试环境"""
        # 清理测试Staff的对话状态
        for staff_id in [self.test_staff_id1, self.test_staff_id2]:
            try:
                # 获取当前参数
                result = _SHARED_STAFF_TOOL.run(
                    action="get",
                    opera_id=self.test_opera_id,
                    staff_id=staff_id
                )
                status_code, staff_data = ApiResponseParser.parse_response(result)
                if status_code == 200:
                    # 清除dialogue_states
                    parameters = json.loads(staff_data.get("parameter", "{}"))
                    if "dialogueStates" in parameters:
                        del parameters["dialogueStates"]
                        # 更新Staff
                        _SHARED_STAFF_TOOL.run(
                            action="update",
                            opera_id=self.test_opera_id,
                            staff_id=staff_id,
                            data={
                                "parameter": json.dumps(parameters)
                            }
                        )
            except Exception as e:
                print(f"清理Staff {staff_id} 时发生错误: {str(e)}")


class TestDialogueAnalysis(AsyncTestCase):
    """测试对话分析功能"""

    def setUp(self):
        """设置测试环境"""
        # 使用已知存在的Opera和Staff ID
        self.test_opera_id1 = UUID('96028f82-9f76-4372-976c-f0c5a054db79')
        self.test_opera_id2 = UUID('99a51bfa-0b95-46e5-96b3-e3cfc021a6b2')  # 另一个Opera
        self.test_staff_id1 = UUID('c2a71833-4403-4d08-8ef6-23e6327832b2')
        self.test_staff_id2 = UUID('06ec00fc-9546-40b0-b180-b482ba0e0e27')

        # 创建测试用的对话池
        self.pool = DialoguePool()

        # 创建测试用的对话 - Opera 1
        self.dialogue1 = ProcessingDialogue(
            dialogue_index=29,
            opera_id=self.test_opera_id1,
            type=DialogueType.NORMAL,
            priority=DialoguePriority.NORMAL,
            status=ProcessingStatus.PENDING,
            receiver_staff_ids=[self.test_staff_id1],
            created_at=datetime.now(timezone(timedelta(hours=8))),
            text="请帮我审查这段代码的性能问题"
        )

        self.dialogue2 = ProcessingDialogue(
            dialogue_index=30,
            opera_id=self.test_opera_id1,
            type=DialogueType.NORMAL,
            priority=DialoguePriority.NORMAL,
            status=ProcessingStatus.PENDING,
            receiver_staff_ids=[self.test_staff_id1],
            created_at=datetime.now(timezone(timedelta(hours=8))),
            text="我发现循环中有一个O(n^2)的复杂度"
        )

        # 创建测试用的对话 - Opera 2
        self.dialogue3 = ProcessingDialogue(
            dialogue_index=1,
            opera_id=self.test_opera_id2,
            type=DialogueType.NORMAL,
            priority=DialoguePriority.NORMAL,
            status=ProcessingStatus.PENDING,
            receiver_staff_ids=[self.test_staff_id2],
            created_at=datetime.now(timezone(timedelta(hours=8))),
            text="这是另一个Opera中的对话"
        )

        # 添加对话到对话池
        self.pool.dialogues = [self.dialogue1, self.dialogue2, self.dialogue3]

    def test_intent_analysis(self):
        """测试意图分析功能"""
        # 执行分析
        self.pool.analyze_dialogues()

        # 验证所有对话都有意图分析结果
        for dialogue in self.pool.dialogues:
            self.assertIsNotNone(dialogue.intent_analysis)
            self.assertIsInstance(dialogue.intent_analysis, IntentAnalysis)
            self.assertIsInstance(dialogue.intent_analysis.intent, str)
            self.assertGreater(len(dialogue.intent_analysis.intent), 0)
            self.assertIsInstance(dialogue.intent_analysis.confidence, float)
            self.assertGreater(dialogue.intent_analysis.confidence, 0)

        # 验证第一个对话的意图是关于代码审查
        self.assertIn("审查", self.dialogue1.intent_analysis.intent.lower())
        self.assertIn("代码", self.dialogue1.intent_analysis.intent.lower())

        # 验证第二个对话的意图是关于性能问题报告
        self.assertIn("性能", self.dialogue2.intent_analysis.intent.lower())
        self.assertIn("复杂度", self.dialogue2.intent_analysis.intent.lower())

    def test_context_analysis(self):
        """测试上下文关联分析功能"""
        # 执行分析
        self.pool.analyze_dialogues()

        # 验证所有对话都有上下文信息
        for dialogue in self.pool.dialogues:
            self.assertIsNotNone(dialogue.context)
            self.assertIsInstance(dialogue.context, DialogueContext)
            self.assertIsInstance(dialogue.context.related_dialogue_indices, list)

        # 验证同一Opera内的对话关联
        # dialogue2应该与dialogue1有关联（因为都是关于代码审查的对话）
        self.assertIn(1, self.dialogue2.context.related_dialogue_indices)

        # 验证不同Opera的对话没有关联
        # dialogue3不应该与dialogue1或dialogue2有关联
        self.assertEqual(len(self.dialogue3.context.related_dialogue_indices), 0)

    def test_opera_isolation(self):
        """测试Opera隔离功能"""
        # 执行分析
        self.pool.analyze_dialogues()

        # 获取每个Opera的对话
        opera1_dialogues = [d for d in self.pool.dialogues if d.opera_id == self.test_opera_id1]
        opera2_dialogues = [d for d in self.pool.dialogues if d.opera_id == self.test_opera_id2]

        # 验证Opera1的对话只与Opera1的对话有关联
        for dialogue in opera1_dialogues:
            related_dialogues = [
                self.pool.get_dialogue(idx)
                for idx in dialogue.context.related_dialogue_indices
            ]
            for related in related_dialogues:
                self.assertEqual(related.opera_id, self.test_opera_id1)

        # 验证Opera2的对话只与Opera2的对话有关联
        for dialogue in opera2_dialogues:
            related_dialogues = [
                self.pool.get_dialogue(idx)
                for idx in dialogue.context.related_dialogue_indices
            ]
            for related in related_dialogues:
                self.assertEqual(related.opera_id, self.test_opera_id2)

    def test_heat_update(self):
        """测试热度更新功能"""
        # 记录初始热度
        initial_heats = {d.dialogue_index: d.heat for d in self.pool.dialogues}

        # 执行分析
        self.pool.analyze_dialogues()

        # 验证相关对话的热度有增加
        for dialogue in self.pool.dialogues:
            if dialogue.context.related_dialogue_indices:
                for related_index in dialogue.context.related_dialogue_indices:
                    related = self.pool.get_dialogue(related_index)
                    self.assertGreater(
                        related.heat,
                        initial_heats[related.dialogue_index]
                    )

    def test_conversation_state(self):
        """测试对话状态信息"""
        # 执行分析
        self.pool.analyze_dialogues()

        # 验证每个对话的状态信息
        for dialogue in self.pool.dialogues:
            state = dialogue.context.conversation_state
            self.assertIn("intent", state)
            self.assertIn("confidence", state)
            self.assertIn("analyzed_at", state)
            self.assertIsInstance(state["intent"], str)
            self.assertIsInstance(state["confidence"], float)
            self.assertIsInstance(state["analyzed_at"], str)

    # def tearDown(self):
    #     """清理测试环境"""
    #     self.run_async(self._tearDown())

    # async def _tearDown(self):
    #     """异步清理测试环境"""
    #     # 清理测试Staff的对话状态
    #     for staff_id in [self.test_staff_id1, self.test_staff_id2]:
    #         try:
    #             # 获取当前参数
    #             result = _SHARED_STAFF_TOOL.run(
    #                 action="get",
    #                 opera_id=self.test_opera_id1,
    #                 staff_id=staff_id
    #             )
    #             status_code, staff_data = ApiResponseParser.parse_response(result)
    #             if status_code == 200:
    #                 # 清除dialogue_states
    #                 parameters = json.loads(staff_data.get("parameter", "{}"))
    #                 if "dialogueStates" in parameters:
    #                     del parameters["dialogueStates"]
    #                     # 更新Staff
    #                     _SHARED_STAFF_TOOL.run(
    #                         action="update",
    #                         opera_id=self.test_opera_id1,
    #                         staff_id=staff_id,
    #                         data=StaffForUpdate(parameter=json.dumps(parameters))
    #                     )
    #         except Exception as e:
    #             print(f"清理Staff {staff_id} 时发生错误: {str(e)}")


if __name__ == '__main__':
    unittest.main()
