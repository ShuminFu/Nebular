import unittest
from uuid import UUID
from datetime import datetime, timezone, timedelta
import json
import asyncio

from src.core.task_utils import (
    BotTask, TaskType, TaskPriority, TaskStatus,
    BotTaskQueue
)
from src.crewai_ext.tools.opera_api.bot_api_tool import _SHARED_BOT_TOOL
from src.core.parser.api_response_parser import ApiResponseParser


class AsyncTestCase(unittest.TestCase):
    def run_async(self, coro):
        return asyncio.run(coro)


class TestBotTaskQueue(AsyncTestCase):
    def setUp(self):
        """设置测试环境"""
        # 使用已知存在的Bot ID
        self.test_bot_id = UUID('4a2d346e-e045-4756-b7a9-a1f825055ee9')

        # 创建测试用的任务队列
        self.queue = BotTaskQueue(bot_id=self.test_bot_id)

        # 创建测试用的任务
        self.task1 = BotTask(
            type=TaskType.CONVERSATION,
            priority=TaskPriority.NORMAL,
            status=TaskStatus.COMPLETED,
            description="Test task 1",
            parameters={"key1": "value1"},
            progress=100,
            created_at=datetime.now(timezone(timedelta(hours=8)))
        )

        self.task2 = BotTask(
            type=TaskType.CHAT_PLANNING,
            priority=TaskPriority.HIGH,
            status=TaskStatus.PENDING,
            description="Test task 2",
            parameters={"key2": "value2"},
            progress=0,
            created_at=datetime.now(timezone(timedelta(hours=8)))
        )

        # 添加任务到队列
        self.queue.tasks = [self.task1, self.task2]

    def test_persist_to_api_success(self):
        """测试成功持久化任务状态到API"""
        self.run_async(self._test_persist_to_api_success())

    async def _test_persist_to_api_success(self):
        # 执行持久化
        await self.queue._persist_to_api()

        # 验证Bot的更新
        result = _SHARED_BOT_TOOL.run(
            action="get",
            bot_id=self.test_bot_id
        )
        status_code, bot_data = ApiResponseParser.parse_response(result)
        self.assertEqual(status_code, 200)

        # 验证DefaultTags中包含任务状态
        default_tags = json.loads(bot_data.get("defaultTags", "{}"))
        self.assertIn("TaskStates", default_tags)
        task_states = default_tags["TaskStates"]
        self.assertEqual(len(task_states), 2)  # 应该有两个任务

        # 验证任务状态的内容
        for task_state in task_states:
            self.assertIn("Type", task_state)
            self.assertIn("Priority", task_state)
            self.assertIn("Status", task_state)
            self.assertIn("Description", task_state)
            self.assertIn("Parameters", task_state)
            self.assertIn("Progress", task_state)

    def test_persist_to_api_with_empty_queue(self):
        """测试持久化空任务队列的情况"""
        self.run_async(self._test_persist_empty_queue())

    async def _test_persist_empty_queue(self):
        # 创建空任务队列
        empty_queue = BotTaskQueue(bot_id=self.test_bot_id)

        # 执行持久化
        await empty_queue._persist_to_api()

        # 验证Bot的状态
        result = _SHARED_BOT_TOOL.run(
            action="get",
            bot_id=self.test_bot_id
        )
        status_code, bot_data = ApiResponseParser.parse_response(result)
        self.assertEqual(status_code, 200)

        # 验证DefaultTags
        default_tags = json.loads(bot_data.get("defaultTags", "{}"))
        if "TaskStates" in default_tags:
            self.assertEqual(len(default_tags["TaskStates"]), 0)

    def test_persist_to_api_with_invalid_bot_id(self):
        """测试使用无效Bot ID的情况"""
        self.run_async(self._test_persist_to_api_with_invalid_bot_id())

    async def _test_persist_to_api_with_invalid_bot_id(self):
        # 创建使用无效Bot ID的任务队列
        invalid_queue = BotTaskQueue(
            bot_id=UUID('00000000-0000-0000-0000-000000000000')
        )
        invalid_queue.tasks = [self.task1, self.task2]

        # 执行持久化
        await invalid_queue._persist_to_api()

        # 验证Bot的状态（应该失败）
        result = _SHARED_BOT_TOOL.run(
            action="get",
            bot_id=UUID('00000000-0000-0000-0000-000000000000')
        )
        status_code, _ = ApiResponseParser.parse_response(result)
        self.assertNotEqual(status_code, 200)

    def tearDown(self):
        """清理测试环境"""
        self.run_async(self._tearDown())

    async def _tearDown(self):
        """异步清理测试环境"""
        try:
            # 获取当前Bot的DefaultTags
            result = _SHARED_BOT_TOOL.run(
                action="get",
                bot_id=self.test_bot_id
            )
            status_code, bot_data = ApiResponseParser.parse_response(result)
            if status_code == 200:
                # 清除taskStates
                default_tags = json.loads(bot_data.get("defaultTags", "{}"))
                if "TaskStates" in default_tags:
                    del default_tags["TaskStates"]
                    # 更新Bot
                    _SHARED_BOT_TOOL.run(
                        action="update",
                        bot_id=self.test_bot_id,
                        data={"defaultTags": json.dumps(default_tags)}
                    )
        except Exception as e:
            print(f"清理Bot {self.test_bot_id} 时发生错误: {str(e)}")


if __name__ == '__main__':
    unittest.main()
