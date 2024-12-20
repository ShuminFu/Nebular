import unittest
from uuid import UUID
from datetime import datetime, timezone, timedelta
import json
import asyncio

from Opera.core.dialogue_utils import (
    ProcessingDialogue, DialogueType, DialoguePool,
    PersistentDialogueState, DialoguePriority, ProcessingStatus
)
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
    def run_async(self, coro):
        return asyncio.run(coro)


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
            text="Test dialogue 1"
        )

        self.dialogue2 = ProcessingDialogue(
            dialogue_index=2,
            opera_id=self.test_opera_id,
            type=DialogueType.WHISPER,
            priority=DialoguePriority.HIGH,
            status=ProcessingStatus.PENDING,
            receiver_staff_ids=[self.test_staff_id1, self.test_staff_id2],
            created_at=datetime.now(timezone(timedelta(hours=8))),
            text="Test dialogue 2"
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


if __name__ == '__main__':
    unittest.main()
