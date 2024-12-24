"""测试任务分发和回调流程"""

from uuid import UUID

from Opera.core.crew_process import CrewManager, CrewRunner, CrewProcessInfo
from Opera.core.task_utils import BotTask, TaskType, TaskStatus, TaskPriority, BotTaskQueue
from Opera.core.tests.test_task_utils import AsyncTestCase


class TestTaskDispatch(AsyncTestCase):
    def setUp(self):
        """设置测试环境"""
        # 创建测试用的Bot IDs
        self.cm_bot_id = UUID('4a2d346e-e045-4756-b7a9-a1f825055ee9')  # CM的Bot ID
        self.cr_bot_id = UUID('894c1763-22b2-418c-9a18-3c40b88d28bc')  # CR的Bot ID
        self.test_opera_id = UUID('96028f82-9f76-4372-976c-f0c5a054db79')  # 测试用Opera ID
        self.user_staff_id = UUID('06ec00fc-9546-40b0-b180-b482ba0e0e27')  # 用户的Staff ID
        self.cm_staff_id = UUID('ab01d4f7-bbf1-44aa-a55b-cbc7d62fbfbc')  # CM的Staff ID
        self.cr_staff_id = UUID('c2a71833-4403-4d08-8ef6-23e6327832b2')  # CR的Staff ID

        # 创建CrewManager实例
        self.crew_manager = CrewManager()
        self.crew_manager.bot_id = self.cm_bot_id
        # 为CM创建任务队列
        self.crew_manager.task_queue = BotTaskQueue(bot_id=self.cm_bot_id)

        # 创建CrewRunner实例
        self.crew_runner = CrewRunner({}, self.cr_bot_id)
        # 为CR创建任务队列
        self.crew_runner.task_queue = BotTaskQueue(bot_id=self.cr_bot_id)

        # 模拟一个CrewRunner进程信息
        self.crew_manager.crew_processes[self.cr_staff_id] = CrewProcessInfo(
            process=None,  # 测试不需要实际的进程
            bot_id=self.cr_bot_id,
            opera_ids=[self.test_opera_id],
            roles={self.test_opera_id: ["assistant"]},
            staff_ids={self.test_opera_id: [self.cr_staff_id]}
        )

        # 缓存CM的staff_id
        self.crew_manager._staff_id_cache[str(self.test_opera_id)] = self.cm_staff_id

    def test_task_dispatch_and_callback(self):
        """测试任务分发和回调的完整流程"""
        self.run_async(self._test_task_dispatch_and_callback())

    async def _test_task_dispatch_and_callback(self):
        # 1. 创建一个测试任务
        original_task = BotTask(
            type=TaskType.CHAT_RESPONSE,
            priority=TaskPriority.NORMAL,
            description="Test task dispatch",
            parameters={
                "text": "Hello, this is a test task",
                "opera_id": str(self.test_opera_id)
            },
            source_staff_id=self.user_staff_id,  # 设置原始用户的staff_id
            response_staff_id=self.cr_staff_id  # 设置响应者为CR
        )

        # 1.1 将原始任务添加到CM的任务队列中
        await self.crew_manager.task_queue.add_task(original_task)

        # 2. CM处理任务（分发给CR）
        await self.crew_manager._process_task(original_task)

        # 3. 手动将任务添加到CR的任务队列（模拟CR从持久化接口读取任务）
        await self.crew_runner.task_queue.add_task(original_task)

        # 4. 模拟CR处理任务
        task = self.crew_runner.task_queue.get_next_task()
        self.assertIsNotNone(task, "CR应该能够获取到任务")
        await self.crew_runner._handle_task_completion(task, "Task completed successfully")

        # 5. 因为还没有实现load_from_api，手动将回调任务添加到CM的任务队列（模拟CM从持久化接口读取任务）
        callback_task = BotTask(
            type=TaskType.CALLBACK,
            priority=TaskPriority.URGENT,
            description=f"Callback for task {original_task.id}",
            parameters={
                "callback_task_id": str(original_task.id),
                "result": "Task completed successfully",
                "opera_id": str(self.test_opera_id)
            },
            source_staff_id=self.cm_staff_id
        )
        await self.crew_manager.task_queue.add_task(callback_task)

        # 6. CM处理回调任务
        callback = self.crew_manager.task_queue.get_next_task()
        self.assertIsNotNone(callback, "CM应该能够获取到回调任务")
        await self.crew_manager._handle_task_callback(callback)

        # 验证任务状态和结果
        # 在CM的任务队列中查找原始任务
        original_task_in_queue = None
        for task in self.crew_manager.task_queue.tasks:
            if task.id == original_task.id:
                original_task_in_queue = task
                break

        self.assertIsNotNone(original_task_in_queue, "原始任务应该在CM的任务队列中")
        self.assertEqual(original_task_in_queue.status, TaskStatus.COMPLETED)

    def tearDown(self):
        """清理测试环境"""
        self.run_async(self._tearDown())

    async def _tearDown(self):
        # 清理缓存
        self.crew_manager._staff_id_cache.clear()
        # 清理进程信息
        self.crew_manager.crew_processes.clear()
        # 清理任务队列
        self.crew_manager.task_queue.tasks.clear()
        self.crew_runner.task_queue.tasks.clear()
