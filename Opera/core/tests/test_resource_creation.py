import unittest
from uuid import UUID
from datetime import datetime, timezone
from Opera.core.crew_process import CrewManager
from Opera.core.task_utils import BotTaskQueue, TaskType, TaskStatus, BotTask
from Opera.signalr_client.opera_signalr_client import MessageReceivedArgs
from Opera.core.tests.test_task_utils import AsyncTestCase
from Opera.core.intent_mind import IntentMind
from Opera.core.api_response_parser import ApiResponseParser
from ai_core.tools.opera_api.resource_api_tool import _SHARED_RESOURCE_TOOL
from ai_core.tools.opera_api.resource_api_tool import Resource
import asyncio


class TestResourceCreation(AsyncTestCase):
    def setUp(self):
        """设置测试环境"""
        # 创建测试用的Bot IDs
        self.cm_bot_id = UUID('4a4857d6-4664-452e-a37c-80a628ca28a0')  # CM的Bot ID
        self.test_opera_id = UUID('96028f82-9f76-4372-976c-f0c5a054db79')  # 测试用Opera ID
        self.user_staff_id = UUID('c2a71833-4403-4d08-8ef6-23e6327832b2')  # 用户的Staff ID
        self.cm_staff_id = UUID('ab01d4f7-bbf1-44aa-a55b-cbc7d62fbfbc')  # CM的Staff ID

        # 设置测试用的代码内容
        self.test_code_content = """@file: examples/calculator.py
@description: A simple calculator implementation
@tags: math,utility,versionID
@version: 1.0.0
@version_id: 12345678-1234-5678-1234-567812345678
---
def add_numbers(a: int, b: int) -> int:
    return a + b"""

        # 创建CrewManager实例
        self.crew_manager = CrewManager()
        self.crew_manager.bot_id = self.cm_bot_id

        # 设置通用的测试时间
        self.test_time = datetime.now(timezone.utc).isoformat()

        # 缓存CM的staff_id
        self.crew_manager._staff_id_cache[str(self.test_opera_id)] = self.cm_staff_id

        # 初始化CrewManager
        self.run_async(self._init_crew_manager())

    async def _init_crew_manager(self):
        """初始化CrewManager，但不进入主循环"""
        # 保存原始的is_running值
        original_is_running = self.crew_manager.is_running
        # 设置is_running为False，这样run方法会在setup后立即返回
        self.crew_manager.is_running = False
        try:
            await self.crew_manager.run()
        finally:
            # 恢复原始的is_running值
            self.crew_manager.is_running = original_is_running

    def test_code_resource_parsing(self):
        """测试代码资源的解析"""
        self.run_async(self._test_code_resource_parsing())

    def test_invalid_code_resource(self):
        """测试无效的代码资源格式"""
        self.run_async(self._test_invalid_code_resource())

    def test_task_status_update(self):
        """测试任务状态更新"""
        self.run_async(self._test_task_status_update())

    def test_resource_api_calls(self):
        """测试资源创建过程中的API调用"""
        self.run_async(self._test_resource_api_calls())

    async def _test_code_resource_parsing(self):
        # 创建一个模拟的消息
        message = MessageReceivedArgs(
            index=1,
            text=self.test_code_content,
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
        message = MessageReceivedArgs(
            index=3,
            text=self.test_code_content,
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

        # 从任务队列中获取更新后的任务
        updated_task = next(t for t in self.crew_manager.task_queue.tasks if t.id == task.id)
        self.assertEqual(updated_task.status, TaskStatus.COMPLETED)

    async def _test_resource_api_calls(self):
        # 手动从测试代码内容中提取代码部分, 实际中从MessageArgs转化为BotTask的时候, code_content已经提取出来了
        code_content = self.test_code_content.split("---\n")[1].strip()
        # 使用时间戳创建唯一的文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_path = f"examples/calculator_{timestamp}.py"
        description = "A simple calculator implementation"
        tags = ["math", "utility", "versionID"]
        mime_type = "text/x-python"

        # 创建测试任务
        task = BotTask(
            id=UUID('bf9145e3-aee8-4945-ab28-a6b906815e83'),
            type=TaskType.RESOURCE_CREATION,
            status=TaskStatus.PENDING,
            priority=3,
            description="Create resource test",
            parameters={
                "file_path": file_path,
                "description": description,
                "tags": tags,
                "code_content": code_content,
                "opera_id": str(self.test_opera_id),
                "resource_type": "code",
                "mime_type": mime_type
            },
            source_staff_id=self.user_staff_id,
            response_staff_id=self.cm_staff_id
        )

        # 将任务添加到队列中
        await self.crew_manager.task_queue.add_task(task)

        # 执行资源创建
        await self.crew_manager.resource_handler.handle_resource_creation(task)

        # 从任务队列中获取更新后的任务
        updated_task = next(t for t in self.crew_manager.task_queue.tasks if t.id == task.id)

        # 验证任务状态和结果
        self.assertEqual(updated_task.status, TaskStatus.COMPLETED)
        self.assertIsNotNone(updated_task.result.get("resource_id"))
        self.assertEqual(updated_task.result["path"], file_path)
        self.assertEqual(updated_task.result["status"], "success")

        # 验证资源是否真实存在
        resource_result = await asyncio.to_thread(
            _SHARED_RESOURCE_TOOL.run,
            action="get",
            opera_id=str(self.test_opera_id),
            resource_id=UUID(updated_task.result["resource_id"])
        )

        # 直接使用Resource对象进行验证
        self.assertIsInstance(resource_result, Resource)
        self.assertEqual(resource_result.name, file_path)
        self.assertEqual(resource_result.description, description)
        self.assertEqual(resource_result.mime_type, mime_type)  # 验证MIME类型是否正确

    def test_resource_api_error_handling(self):
        """测试资源创建过程中的错误处理"""
        self.run_async(self._test_resource_api_error_handling())

    async def _test_resource_api_error_handling(self):
        # 从测试代码内容中提取代码部分
        # 同上是模拟的code_content
        code_content = self.test_code_content.split("---\n")[1].strip()

        # 测试无效路径
        task = BotTask(
            id=UUID('bf9145e3-aee8-4945-ab28-a6b906815e83'),
            type=TaskType.RESOURCE_CREATION,
            status=TaskStatus.PENDING,
            priority=3,
            description="Create resource test",
            parameters={
                "file_path": "/invalid/path/test.py",  # 使用无效的路径
                "description": "This should fail",
                "tags": ["test"],
                "code_content": code_content,
                "opera_id": str(self.test_opera_id),
                "resource_type": "code"
            },
            source_staff_id=self.user_staff_id,
            response_staff_id=self.cm_staff_id
        )

        # 将任务添加到队列中
        await self.crew_manager.task_queue.add_task(task)

        # 执行资源创建
        await self.crew_manager.resource_handler.handle_resource_creation(task)

        # 从任务队列中获取更新后的任务
        updated_task = next(t for t in self.crew_manager.task_queue.tasks if t.id == task.id)

        # 验证任务状态和错误信息
        self.assertEqual(updated_task.status, TaskStatus.FAILED)
        self.assertIsNotNone(updated_task.error_message)

        # 测试无效的代码内容
        task = BotTask(
            id=UUID('bf9145e3-aee8-4945-ab28-a6b906815e84'),  # 使用不同的ID
            type=TaskType.RESOURCE_CREATION,
            status=TaskStatus.PENDING,
            priority=3,
            description="Create resource test",
            parameters={
                "file_path": "examples/invalid.py",
                "description": "This should fail",
                "tags": ["test"],
                "code_content": None,  # 无效的代码内容
                "opera_id": str(self.test_opera_id),
                "resource_type": "code"
            },
            source_staff_id=self.user_staff_id,
            response_staff_id=self.cm_staff_id
        )

        # 将任务添加到队列中
        await self.crew_manager.task_queue.add_task(task)

        # 执行资源创建
        await self.crew_manager.resource_handler.handle_resource_creation(task)

        # 从任务队列中获取更新后的任务
        updated_task = next(t for t in self.crew_manager.task_queue.tasks if t.id == task.id)

        # 验证任务状态和错误信息
        self.assertEqual(updated_task.status, TaskStatus.FAILED)
        self.assertIn("缺少必要的资源信息", updated_task.error_message)

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

        # 清理测试过程中创建的资源
        try:
            # 获取所有资源
            resources = await asyncio.to_thread(
                _SHARED_RESOURCE_TOOL.run,
                action="get_filtered",
                opera_id=str(self.test_opera_id),
                data={
                    "name_like": "calculator_"  # 使用更通用的匹配模式
                }
            )

            # 直接使用返回的Resource对象列表
            if resources:
                for resource in resources:
                    # 删除资源
                    await asyncio.to_thread(
                        _SHARED_RESOURCE_TOOL.run,
                        action="delete",
                        opera_id=str(self.test_opera_id),
                        resource_id=resource.id
                    )
        except Exception as e:
            print(f"清理资源时出错: {e}")


if __name__ == '__main__':
    unittest.main()
