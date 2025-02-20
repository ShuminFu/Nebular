# import asyncio
# import unittest
# from unittest.mock import AsyncMock, MagicMock, patch
# from uuid import UUID
# import pytest

# from src.core.crew_process import BaseCrewProcess, CrewManager, CrewRunner
# from src.core.task_utils import BotTask, TaskType, TaskStatus, TaskPriority, BotTaskQueue
# from src.opera_service.signalr_client.opera_signalr_client import MessageReceivedArgs
# from crewai import Crew


# class AsyncTestCase(unittest.TestCase):
#     """基础异步测试类"""

#     def setUp(self):
#         self.loop = asyncio.new_event_loop()
#         asyncio.set_event_loop(self.loop)

#     def tearDown(self):
#         self.loop.close()

#     def async_run(self, coro):
#         return self.loop.run_until_complete(coro)


# @pytest.mark.usefixtures("loop")
# class TestCrewProcess(BaseCrewProcess):
#     """用于测试的具体CrewProcess实现"""

#     def _setup_crew(self) -> Crew:
#         return MagicMock()

#     async def _handle_conversation_task(self, task: BotTask):
#         pass

#     async def _handle_generation_task(self, task: BotTask):
#         pass


# @pytest.mark.asyncio
# class TestBaseCrewProcess(AsyncTestCase):
#     """测试BaseCrewProcess的核心异步功能"""

#     def setUp(self):
#         super().setUp()
#         self.bot_id = UUID("7c80efe6-a18a-43f5-8bc8-853a29d78bd7")
#         self.process = TestCrewProcess()  # 使用测试实现类
#         self.process.bot_id = self.bot_id
#         self.process.task_queue = BotTaskQueue(bot_id=self.bot_id)

#     @pytest.mark.asyncio
#     async def test_setup_and_connection(self):
#         """测试SignalR连接设置和状态"""
#         # 模拟SignalR客户端
#         with patch("src.opera_service.signalr_client.opera_signalr_client.OperaSignalRClient") as mock_client:
#             mock_client.return_value._connected = True
#             mock_client.return_value.connect = AsyncMock()
#             mock_client.return_value.set_callback = MagicMock()

#             # 运行setup
#             await self.process.setup()

#             # 验证连接和回调设置
#             mock_client.return_value.connect.assert_called_once()
#             self.assertEqual(mock_client.return_value.set_callback.call_count, 2)  # on_hello 和 on_message_received

#     @pytest.mark.asyncio
#     async def test_message_handling(self):
#         """测试消息处理和任务创建"""
#         # 模拟SignalR消息
#         message = MessageReceivedArgs(
#             opera_id="test-opera",
#             staff_id="test-staff",
#             text="测试消息",
#             is_narratage=False,
#             is_whisper=False,
#             mentioned_staff_ids=None,
#         )

#         # 模拟intent processor
#         self.process.intent_processor = AsyncMock()

#         # 处理消息
#         await self.process._handle_message(message)

#         # 验证intent processor被调用
#         self.process.intent_processor.process_message.assert_called_once_with(message)

#     @pytest.mark.asyncio
#     async def test_run_loop_not_blocking(self):
#         """测试主循环不会阻塞"""
#         # 设置mock
#         with patch("asyncio.gather") as mock_gather:
#             self.process.setup = AsyncMock()
#             self.process.stop = AsyncMock()
#             mock_gather.return_value = None

#             # 运行一个短暂的循环
#             self.process.is_running = True

#             async def stop_after_delay():
#                 await asyncio.sleep(0.1)
#                 self.process.is_running = False

#             # 同时运行主循环和延迟停止
#             await asyncio.gather(self.process.run(), stop_after_delay())

#             # 验证gather被调用
#             self.assertTrue(mock_gather.called)


# @pytest.mark.asyncio
# class TestCrewManager(AsyncTestCase):
#     """测试CrewManager特定功能"""

#     def setUp(self):
#         super().setUp()
#         self.manager = CrewManager()
#         self.manager.bot_id = UUID("7c80efe6-a18a-43f5-8bc8-853a29d78bd7")
#         self.manager.task_queue = BotTaskQueue(bot_id=self.manager.bot_id)

#     @pytest.mark.asyncio
#     async def test_task_forwarding(self):
#         """测试任务转发到CrewRunner"""
#         # 创建一个测试任务
#         task = BotTask(
#             id=UUID("87654321-4321-8765-4321-876543210987"),
#             type=TaskType.CONVERSATION,
#             priority=TaskPriority.NORMAL,
#             parameters={"opera_id": "test-opera"},
#             response_staff_id=UUID("98765432-5432-9876-5432-987654321098"),
#         )

#         # 模拟CrewRunner进程信息
#         self.manager.crew_processes = {task.response_staff_id: MagicMock(bot_id=UUID("11111111-1111-1111-1111-111111111111"))}

#         # 模拟_update_cr_task_queue方法
#         self.manager._update_cr_task_queue = AsyncMock()

#         # 处理任务
#         await self.manager._process_task(task)

#         # 验证任务转发
#         self.manager._update_cr_task_queue.assert_called_once()


# @pytest.mark.asyncio
# class TestCrewRunner(AsyncTestCase):
#     """测试CrewRunner特定功能"""

#     def setUp(self):
#         super().setUp()
#         self.runner = CrewRunner(
#             bot_id=UUID("12345678-1234-5678-1234-567812345678"), parent_bot_id=UUID("87654321-4321-8765-4321-876543210987")
#         )
#         self.runner.task_queue = BotTaskQueue(bot_id=self.runner.bot_id)

#     @pytest.mark.asyncio
#     async def test_conversation_task_processing(self):
#         """测试对话任务处理"""
#         # 创建测试任务
#         task = BotTask(
#             id=UUID("87654321-4321-8765-4321-876543210987"),
#             type=TaskType.CONVERSATION,
#             priority=TaskPriority.NORMAL,
#             parameters={
#                 "opera_id": "test-opera",
#                 "text": "测试对话",
#                 "context": {"stage_index": 1, "conversation_state": {}, "flow": {}, "code_context": {}},
#             },
#         )

#         # 模拟chat_crew
#         with patch("src.crewai_ext.crew_bases.runner_crewbase.RunnerChatCrew") as mock_chat_crew:
#             mock_crew_instance = MagicMock()
#             mock_crew_instance.crew.return_value.kickoff_async = AsyncMock(return_value=MagicMock(raw="测试回复"))
#             mock_chat_crew.return_value = mock_crew_instance
#             self.runner.chat_crew = mock_chat_crew.return_value

#             # 处理任务
#             with patch("src.crewai_ext.tools.opera_api.dialogue_api_tool._SHARED_DIALOGUE_TOOL") as mock_dialogue_tool:
#                 mock_dialogue_tool.run.return_value = {"statusCode": 200}
#                 await self.runner._handle_conversation_task(task)

#             # 验证任务处理
#             mock_crew_instance.crew.return_value.kickoff_async.assert_called_once()
#             self.assertEqual(task.status, TaskStatus.COMPLETED)


# if __name__ == "__main__":
#     pytest.main(["-v", "--asyncio-mode=auto"])
