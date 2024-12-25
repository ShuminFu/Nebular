import unittest
from uuid import UUID
import json
from Opera.core.intent_mind import IntentMind
from Opera.core.task_utils import BotTaskQueue, TaskType, TaskStatus
from Opera.signalr_client.opera_signalr_client import MessageReceivedArgs


class TestResourceCreation(unittest.TestCase):
    def setUp(self):
        # 初始化测试环境
        self.bot_id = UUID('4a4857d6-4664-452e-a37c-80a628ca28a0')
        self.task_queue = BotTaskQueue(bot_id=self.bot_id)
        self.intent_mind = IntentMind(self.task_queue)

    def test_code_resource_parsing(self):
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
            sender_staff_id=UUID('c2a71833-4403-4d08-8ef6-23e6327832b2'),
            opera_id=UUID('96028f82-9f76-4372-976c-f0c5a054db79'),
            is_whisper=False,
            is_narratage=False,
            mentioned_staff_ids=None
        )

        # 处理消息
        self.intent_mind._process_single_message(message)

        # 获取创建的任务
        task = self.task_queue.get_next_task()

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

    def test_invalid_code_resource(self):
        # 测试无效的代码资源格式
        invalid_content = """This is not a valid code resource format
def some_function():
    pass"""

        message = MessageReceivedArgs(
            index=2,
            text=invalid_content,
            tags="code_resource",
            sender_staff_id=UUID('c2a71833-4403-4d08-8ef6-23e6327832b2'),
            opera_id=UUID('96028f82-9f76-4372-976c-f0c5a054db79'),
            is_whisper=False,
            is_narratage=False,
            mentioned_staff_ids=None
        )

        # 处理消息
        self.intent_mind._process_single_message(message)

        # 获取创建的任务
        task = self.task_queue.get_next_task()

        # 验证任务类型是否为错误
        self.assertEqual(task.type, TaskType.ERROR)

    def test_task_status_update(self):
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
            sender_staff_id=UUID('c2a71833-4403-4d08-8ef6-23e6327832b2'),
            opera_id=UUID('96028f82-9f76-4372-976c-f0c5a054db79'),
            is_whisper=False,
            is_narratage=False,
            mentioned_staff_ids=None
        )

        # 处理消息
        self.intent_mind._process_single_message(message)

        # 获取任务
        task = self.task_queue.get_next_task()

        # 验证初始状态
        self.assertEqual(task.status, TaskStatus.PENDING)

        # 更新任务状态
        self.task_queue.update_task_status(task.id, TaskStatus.COMPLETED)

        # 验证更新后的状态
        updated_task = next(t for t in self.task_queue.tasks if t.id == task.id)
        self.assertEqual(updated_task.status, TaskStatus.COMPLETED)


if __name__ == '__main__':
    unittest.main()
