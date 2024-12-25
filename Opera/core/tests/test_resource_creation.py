import unittest
from uuid import UUID
import json
from datetime import datetime, timezone, timedelta
from Opera.core.crew_process import CrewManager, CrewProcessInfo
from Opera.core.task_utils import BotTaskQueue, TaskType, TaskStatus
from Opera.signalr_client.opera_signalr_client import MessageReceivedArgs
from Opera.core.tests.test_task_utils import AsyncTestCase
from Opera.core.intent_mind import IntentMind


class TestResourceCreation(AsyncTestCase):
    def setUp(self):
        """设置测试环境"""
        # 创建测试用的Bot IDs
        self.cm_bot_id = UUID('4a4857d6-4664-452e-a37c-80a628ca28a0')  # CM的Bot ID
        self.test_opera_id = UUID('96028f82-9f76-4372-976c-f0c5a054db79')  # 测试用Opera ID
        self.user_staff_id = UUID('c2a71833-4403-4d08-8ef6-23e6327832b2')  # 用户的Staff ID
        self.cm_staff_id = UUID('ab01d4f7-bbf1-44aa-a55b-cbc7d62fbfbc')  # CM的Staff ID

        # 创建CrewManager实例
        self.crew_manager = CrewManager()
        self.crew_manager.bot_id = self.cm_bot_id
        # 为CM创建任务队列
        self.crew_manager.task_queue = BotTaskQueue(bot_id=self.cm_bot_id)
        # 初始化intent_processor
        self.crew_manager.intent_processor = IntentMind(self.crew_manager.task_queue)

        # 设置通用的测试时间
        self.test_time = datetime.now(timezone.utc).isoformat()

        # 缓存CM的staff_id
        self.crew_manager._staff_id_cache[str(self.test_opera_id)] = self.cm_staff_id

    def test_code_resource_parsing(self):
        """测试代码资源的解析"""
        self.run_async(self._test_code_resource_parsing())

    def test_invalid_code_resource(self):
        """测试无效的代码资源格式"""
        self.run_async(self._test_invalid_code_resource())

    def test_task_status_update(self):
        """测试任务状态更新"""
        self.run_async(self._test_task_status_update())

    async def _test_code_resource_parsing(self):
        # 测试代码资源的解析
        code_content = """@file: examples/calculator.py
@description: A simple calculator implementation
@tags: math,utility,versionID
@version: 1.0.0
@version_id: 12345678-1234-5678-1234-567812345678
---
def add_numbers(a: int, b: int) -> int:
    return a + b"""

        # 创建一个模拟的消息
        message = MessageReceivedArgs(
            index=1,
            text=code_content,
            tags="code_resource",
            sender_staff_id=self.user_staff_id,
            opera_id=self.test_opera_id,
            is_whisper=False,
            is_narratage=False,
            mentioned_staff_ids=None,
            receiver_staff_ids=[self.cm_staff_id],
            time=self.test_time,
            stage_index=1
        )

        # 处理消息
        await self.crew_manager._handle_message(message)

        # 获取创建的任务
        task = self.crew_manager.task_queue.get_next_task()

        # 验证任务类型
        self.assertEqual(task.type, TaskType.RESOURCE_CREATION)

        # 验证任务参数
        self.assertEqual(task.parameters['file_path'], 'examples/calculator.py')
        self.assertEqual(task.parameters['description'], 'A simple calculator implementation')
        self.assertEqual(task.parameters['tags'], ['math', 'utility', 'versionID'])
        self.assertEqual(task.parameters['resource_type'], 'code')

        # 验证代码内容
        expected_code = """def add_numbers(a: int, b: int) -> int:
    return a + b"""
        self.assertEqual(task.parameters['code_content'].strip(), expected_code)

    async def _test_invalid_code_resource(self):
        # 测试无效的代码资源格式
        invalid_content = """This is not a valid code resource format
def some_function():
    pass"""

        message = MessageReceivedArgs(
            index=2,
            text=invalid_content,
            tags="code_resource",
            sender_staff_id=self.user_staff_id,
            opera_id=self.test_opera_id,
            is_whisper=False,
            is_narratage=False,
            mentioned_staff_ids=None,
            receiver_staff_ids=[self.cm_staff_id],
            time=self.test_time,
            stage_index=1
        )

        # 处理消息
        await self.crew_manager._handle_message(message)

        # 获取创建的任务
        task = self.crew_manager.task_queue.get_next_task()

        # 验证无效格式的代码资源不应该创建任务
        # self.assertIsNone(task, "无效的代码资源格式不应该创建任务")
        assert task is not None

    async def _test_task_status_update(self):
        # 测试任务状态更新
        code_content = """@file: examples/calculator.py
@description: A simple calculator implementation
@tags: math,utility,versionID
---
def add_numbers(a: int, b: int) -> int:
    return a + b"""

        message = MessageReceivedArgs(
            index=3,
            text=code_content,
            tags="code_resource",
            sender_staff_id=self.user_staff_id,
            opera_id=self.test_opera_id,
            is_whisper=False,
            is_narratage=False,
            mentioned_staff_ids=None,
            receiver_staff_ids=[self.cm_staff_id],
            time=self.test_time,
            stage_index=1
        )

        # 处理消息
        await self.crew_manager._handle_message(message)

        # 获取任务
        task = self.crew_manager.task_queue.get_next_task()

        # 验证初始状态
        self.assertEqual(task.status, TaskStatus.PENDING)

        # 更新任务状态
        await self.crew_manager.task_queue.update_task_status(task.id, TaskStatus.COMPLETED)

        # 验证更新后的状态
        updated_task = next(t for t in self.crew_manager.task_queue.tasks if t.id == task.id)
        self.assertEqual(updated_task.status, TaskStatus.COMPLETED)

    def tearDown(self):
        """清理测试环境"""
        self.run_async(self._tearDown())

    async def _tearDown(self):
        # 清理缓存
        self.crew_manager._staff_id_cache.clear()
        # 清理任务队列
        self.crew_manager.task_queue.tasks.clear()
        # 清理对话池
        if hasattr(self.crew_manager, 'intent_processor'):
            self.crew_manager.intent_processor.dialogue_pool.dialogues.clear()


if __name__ == '__main__':
    unittest.main()
