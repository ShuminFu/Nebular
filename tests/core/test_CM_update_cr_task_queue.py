import unittest
from unittest import mock
import json
from uuid import UUID
from datetime import datetime, timezone, timedelta

from src.core.crew_process import CrewManager, CrewProcessInfo
from src.core.task_utils import BotTask, TaskType, TaskStatus, TaskPriority


class TestCrewManagerProcessTask(unittest.TestCase):
    """测试CrewManager的_process_task方法"""

    def setUp(self):
        """设置测试环境和模拟数据"""
        # 创建CrewManager实例并模拟其依赖项
        self.cm = CrewManager()
        self.cm.crew_processes = {}
        self.cm.log = mock.MagicMock()
        self.cm.task_queue = mock.MagicMock()
        self.cm.resource_handler = mock.MagicMock()
        self.cm.topic_tracker = mock.MagicMock()

        # 创建BotTaskQueue中的任务数据
        self.task1 = BotTask(
            id=UUID("d721473b-733b-44a0-85ab-7f595f6b1271"),
            created_at=datetime(2025, 2, 25, 13, 57, 54, 49881, tzinfo=timezone(timedelta(seconds=28800))),
            started_at=datetime(2025, 2, 25, 13, 59, 19, 526620, tzinfo=timezone(timedelta(seconds=28800))),
            completed_at=None,
            priority=TaskPriority.HIGH,
            type=TaskType.RESOURCE_GENERATION,
            status=TaskStatus.RUNNING,
            description="生成代码文件: /src/html/index.html",
            parameters={
                "file_path": "/src/html/index.html",
                "file_type": "html",
                "mime_type": "text/html",
                "description": "智慧物流官网的主页面",
                "references": ["style.css", "main.js"],
                "code_details": {
                    "project_type": "web",
                    "project_description": "智慧物流官网，用于展示智慧物流相关的功能和信息。",
                    "requirements": ["设计智慧物流相关页面", "提供响应式设计支持", "实现基本站点导航和数据展示"],
                    "frameworks": ["react", "normalize.css"],
                    "resources": [
                        {
                            "file_path": "/src/html/index.html",
                            "type": "html",
                            "mime_type": "text/html",
                            "description": "智慧物流官网的主页面",
                            "references": ["style.css", "main.js"],
                        },
                        {
                            "file_path": "/src/css/style.css",
                            "type": "css",
                            "mime_type": "text/css",
                            "description": "主页面的样式文件",
                        },
                        {
                            "file_path": "/src/js/main.js",
                            "type": "javascript",
                            "mime_type": "text/javascript",
                            "description": "主页面的交互逻辑",
                        },
                    ],
                },
                "dialogue_context": {
                    "text": "写一个智慧物流的官网网站",
                    "type": "CODE_RESOURCE",
                    "tags": "code_request,code_type_javascript,code_type_css,code_type_html,framework_normalize.css,framework_react",
                },
                "opera_id": "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2",
                "parent_topic_id": "0",
            },
            source_dialogue_index=8,
            response_staff_id=UUID("c1541b83-4ce5-4a68-b492-596982adf71d"),
            source_staff_id=UUID("5dbe6ee3-bc88-4718-a352-5bb151b5f428"),
            topic_id="75920714-da41-46f1-ba59-9cd0b524f401",
            topic_type="CODE_RESOURCE",
            progress=0,
            result=None,
            error_message=None,
            retry_count=0,
            last_retry_at=None,
        )

        self.task2 = BotTask(
            id=UUID("0482b442-5756-456f-a7c8-9f0e76c6c357"),
            created_at=datetime(2025, 2, 25, 13, 57, 55, 631366, tzinfo=timezone(timedelta(seconds=28800))),
            started_at=datetime(2025, 2, 25, 13, 59, 19, 594144, tzinfo=timezone(timedelta(seconds=28800))),
            completed_at=None,
            priority=TaskPriority.HIGH,
            type=TaskType.RESOURCE_GENERATION,
            status=TaskStatus.RUNNING,
            description="生成代码文件: /src/css/style.css",
            parameters={
                "file_path": "/src/css/style.css",
                "file_type": "css",
                "mime_type": "text/css",
                "description": "主页面的样式文件",
                "references": [],
                "code_details": {
                    "project_type": "web",
                    "project_description": "智慧物流官网，用于展示智慧物流相关的功能和信息。",
                    "resources": [
                        {
                            "file_path": "/src/html/index.html",
                            "type": "html",
                            "mime_type": "text/html",
                            "description": "智慧物流官网的主页面",
                            "references": ["style.css", "main.js"],
                        },
                        {
                            "file_path": "/src/css/style.css",
                            "type": "css",
                            "mime_type": "text/css",
                            "description": "主页面的样式文件",
                        },
                        {
                            "file_path": "/src/js/main.js",
                            "type": "javascript",
                            "mime_type": "text/javascript",
                            "description": "主页面的交互逻辑",
                        },
                    ],
                },
                "opera_id": "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2",
            },
            response_staff_id=UUID("7cf52904-3248-4ff1-beda-9c7af3317350"),
            source_staff_id=UUID("5dbe6ee3-bc88-4718-a352-5bb151b5f428"),
            topic_id="75920714-da41-46f1-ba59-9cd0b524f401",
            topic_type="CODE_RESOURCE",
        )

        self.task3 = BotTask(
            id=UUID("d77a1734-a108-4b66-9fc7-721641830753"),
            created_at=datetime(2025, 2, 25, 13, 57, 57, 767044, tzinfo=timezone(timedelta(seconds=28800))),
            started_at=datetime(2025, 2, 25, 13, 59, 19, 666475, tzinfo=timezone(timedelta(seconds=28800))),
            completed_at=None,
            priority=TaskPriority.HIGH,
            type=TaskType.RESOURCE_GENERATION,
            status=TaskStatus.RUNNING,
            description="生成代码文件: /src/js/main.js",
            parameters={
                "file_path": "/src/js/main.js",
                "file_type": "javascript",
                "mime_type": "text/javascript",
                "description": "主页面的交互逻辑",
                "opera_id": "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2",
            },
            response_staff_id=UUID("7cf52904-3248-4ff1-beda-9c7af3317350"),
            source_staff_id=UUID("5dbe6ee3-bc88-4718-a352-5bb151b5f428"),
            topic_id="75920714-da41-46f1-ba59-9cd0b524f401",
            topic_type="CODE_RESOURCE",
        )

    @mock.patch("src.core.crew_process.BaseCrewProcess._process_task")
    async def test_process_task_delegates_to_base_for_resource_generation(self, mock_base_process):
        """测试RESOURCE_GENERATION类型任务会委托给基类处理"""
        # 将mock设置为AsyncMock以支持await
        mock_base_process.side_effect = mock.AsyncMock()

        # 执行测试
        await self.cm._process_task(self.task1)

        # 验证基类的_process_task被调用
        mock_base_process.assert_called_once_with(self.task1)

    async def test_process_task_forwards_to_cr(self):
        """测试任务会被转发给对应的CR进程"""
        # 创建一个模拟的CR进程信息
        cr_bot_id = UUID("test-cr-bot-id")
        cr_process = CrewProcessInfo(
            process=mock.MagicMock(), bot_id=cr_bot_id, crew_config={}, opera_ids=[], roles={}, staff_ids={}
        )

        # 设置CM的crew_processes，让task1的response_staff_id匹配CR
        self.cm.crew_processes = {self.task1.response_staff_id: cr_process}

        # 模拟_update_cr_task_queue方法
        self.cm._update_cr_task_queue = mock.AsyncMock()

        # 执行测试
        await self.cm._process_task(self.task1)

        # 验证_update_cr_task_queue被正确调用
        self.cm._update_cr_task_queue.assert_called_once_with(cr_bot_id, self.task1)

    async def test_process_task_forwards_by_staff_id_lookup(self):
        """测试通过遍历staff_ids查找并转发任务给对应的CR进程"""
        # 创建三个模拟的CR进程信息
        opera_id = "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2"
        staff_id1 = UUID("c1541b83-4ce5-4a68-b492-596982adf71d")
        staff_id2 = UUID("7cf52904-3248-4ff1-beda-9c7af3317350")
        staff_id3 = UUID("aa3e60de-e1cb-422d-87dd-6dc35a51e06a")

        cr_bot_id1 = UUID("345a8e66-838d-4c8c-8f9c-730b54d7c20e")
        cr_bot_id2 = UUID("a8350798-fb2e-4149-b366-717be826548f")
        cr_bot_id3 = UUID("bb39ca84-73b5-40e2-8993-4ab07c2f70eb")

        cr_process1 = CrewProcessInfo(
            process=mock.MagicMock(),
            bot_id=cr_bot_id1,
            crew_config={},
            opera_ids=[UUID(opera_id)],
            roles={opera_id: [[""]]},
            staff_ids={opera_id: [staff_id1]},
        )

        cr_process2 = CrewProcessInfo(
            process=mock.MagicMock(),
            bot_id=cr_bot_id2,
            crew_config={},
            opera_ids=[UUID(opera_id)],
            roles={opera_id: [[""]]},
            staff_ids={opera_id: [staff_id3]},
        )

        cr_process3 = CrewProcessInfo(
            process=mock.MagicMock(),
            bot_id=cr_bot_id3,
            crew_config={},
            opera_ids=[UUID(opera_id)],
            roles={opera_id: [[""]]},
            staff_ids={opera_id: [staff_id2]},
        )

        # 设置CM的crew_processes
        self.cm.crew_processes = {cr_bot_id1: cr_process1, cr_bot_id2: cr_process2, cr_bot_id3: cr_process3}

        # 模拟_update_cr_task_queue方法
        self.cm._update_cr_task_queue = mock.AsyncMock()

        # 测试转发task1到cr_process1
        await self.cm._process_task(self.task1)
        self.cm._update_cr_task_queue.assert_called_once_with(cr_bot_id1, self.task1)
        self.cm._update_cr_task_queue.reset_mock()

        # 测试转发task2到cr_process3
        await self.cm._process_task(self.task2)
        self.cm._update_cr_task_queue.assert_called_once_with(cr_bot_id3, self.task2)

    async def test_process_task_handles_resource_creation(self):
        """测试处理RESOURCE_CREATION类型任务"""
        # 创建一个资源创建任务
        task = mock.MagicMock(type=TaskType.RESOURCE_CREATION, topic_id="test-topic-id")

        # 执行测试
        await self.cm._process_task(task)

        # 验证topic_tracker和resource_handler被正确调用
        self.cm.topic_tracker.add_task.assert_called_once_with(task)
        self.cm.resource_handler.handle_resource_creation.assert_called_once_with(task)

    async def test_process_task_handles_resource_iteration_with_resources(self):
        """测试处理含有ResourcesForViewing的RESOURCE_ITERATION任务"""
        # 创建tags数据
        tags_data = {
            "ResourcesForViewing": {
                "Resources": [
                    {"Url": "/src/html/index.html", "ResourceId": "res1"},
                    {"Url": "/src/css/style.css", "ResourceId": "res2"},
                ]
            }
        }

        # 创建一个资源迭代任务
        task = mock.MagicMock(
            type=TaskType.RESOURCE_ITERATION,
            id=UUID("test-task-id"),
            parameters={"text": "迭代需求", "tags": json.dumps(tags_data)},
        )

        # 模拟IterationAnalyzerCrew
        mock_analyzer = mock.MagicMock()
        mock_crew = mock.MagicMock()
        mock_analyzer.crew.return_value = mock_crew
        mock_crew.kickoff_async = mock.AsyncMock(return_value=mock.MagicMock(raw="分析结果"))

        with mock.patch("src.core.crew_process.IterationAnalyzerCrew", return_value=mock_analyzer):
            # 执行测试
            await self.cm._process_task(task)

            # 验证IterationAnalyzerCrew被正确初始化并调用
            mock_crew.kickoff_async.assert_called_once()

            # 验证传递给IterationAnalyzerCrew的参数
            call_args = mock_crew.kickoff_async.call_args[1]["inputs"]
            self.assertEqual(call_args["iteration_requirement"], "迭代需求")
            self.assertEqual(len(call_args["resource_list"]), 2)
            self.assertEqual(call_args["resource_list"][0]["file_path"], "/src/html/index.html")
            self.assertEqual(call_args["resource_list"][0]["resource_id"], "res1")
            self.assertEqual(call_args["resource_list"][1]["file_path"], "/src/css/style.css")
            self.assertEqual(call_args["resource_list"][1]["resource_id"], "res2")

    async def test_process_task_handles_resource_iteration_with_selected_texts(self):
        """测试处理含有SelectedTextsFromViewer的RESOURCE_ITERATION任务"""
        # 创建tags数据
        tags_data = {"SelectedTextsFromViewer": [{"VersionId": "version1"}]}

        # 创建一个资源迭代任务
        task = mock.MagicMock(
            type=TaskType.RESOURCE_ITERATION,
            id=UUID("test-task-id"),
            parameters={"text": "迭代需求", "tags": json.dumps(tags_data)},
        )

        # 模拟topic_tracker.get_topic_info
        topic_info = mock.MagicMock()
        topic_info.current_version.current_files = [
            {"file_path": "/src/html/index.html", "resource_id": "res1"},
            {"file_path": "/src/css/style.css", "resource_id": "res2"},
        ]
        self.cm.topic_tracker.get_topic_info.return_value = topic_info

        # 模拟IterationAnalyzerCrew
        mock_analyzer = mock.MagicMock()
        mock_crew = mock.MagicMock()
        mock_analyzer.crew.return_value = mock_crew
        mock_crew.kickoff_async = mock.AsyncMock(return_value=mock.MagicMock(raw="分析结果"))

        with mock.patch("src.core.crew_process.IterationAnalyzerCrew", return_value=mock_analyzer):
            # 执行测试
            await self.cm._process_task(task)

            # 验证topic_tracker.get_topic_info被调用
            self.cm.topic_tracker.get_topic_info.assert_called_once_with("version1")

            # 验证IterationAnalyzerCrew被正确调用
            mock_crew.kickoff_async.assert_called_once()

            # 验证传递给IterationAnalyzerCrew的参数
            call_args = mock_crew.kickoff_async.call_args[1]["inputs"]
            self.assertEqual(len(call_args["resource_list"]), 2)

    async def test_process_task_handles_resource_iteration_error(self):
        """测试RESOURCE_ITERATION处理失败时的情况"""
        # 创建tags数据
        tags_data = {"SelectedTextsFromViewer": [{"VersionId": "version1"}]}

        # 创建一个资源迭代任务
        task = mock.MagicMock(
            type=TaskType.RESOURCE_ITERATION,
            id=UUID("test-task-id"),
            parameters={"text": "迭代需求", "tags": json.dumps(tags_data)},
        )

        # 模拟topic_tracker.get_topic_info抛出异常
        self.cm.topic_tracker.get_topic_info.side_effect = Exception("模拟获取主题信息失败")

        # 执行测试
        await self.cm._process_task(task)

        # 验证错误被记录
        self.cm.log.error.assert_called()

        # 验证任务状态被更新为失败
        self.cm.task_queue.update_task_status.assert_called_once_with(task.id, TaskStatus.FAILED)

    async def test_process_task_handles_resource_iteration_with_mentionedFromViewer(self):
        """测试处理含有ResourcesMentionedFromViewer的RESOURCE_ITERATION任务"""
        # 创建tags数据
        tags_data = {
            "ResourcesMentionedFromViewer": {
                "Resources": [
                    {"Url": "/src/html/index.html", "ResourceId": "res1"},
                    {"Url": "/src/css/style.css", "ResourceId": "res2"},
                ]
            }
        }

        # 创建一个资源迭代任务
        task = mock.MagicMock(
            type=TaskType.RESOURCE_ITERATION,
            id=UUID("test-task-id"),
            parameters={"text": "迭代需求", "tags": json.dumps(tags_data)},
        )

        # 模拟IterationAnalyzerCrew
        mock_analyzer = mock.MagicMock()
        mock_crew = mock.MagicMock()
        mock_analyzer.crew.return_value = mock_crew
        mock_crew.kickoff_async = mock.AsyncMock(return_value=mock.MagicMock(raw="分析结果"))

        with mock.patch("src.core.crew_process.IterationAnalyzerCrew", return_value=mock_analyzer):
            # 执行测试
            await self.cm._process_task(task)

            # 验证IterationAnalyzerCrew被正确调用
            mock_crew.kickoff_async.assert_called_once()

            # 验证传递给IterationAnalyzerCrew的参数
            call_args = mock_crew.kickoff_async.call_args[1]["inputs"]
            self.assertEqual(len(call_args["resource_list"]), 2)

    async def test_process_task_handles_duplicated_resources(self):
        """测试处理含有重复资源的RESOURCE_ITERATION任务"""
        # 创建带有重复资源的tags数据
        tags_data = {
            "ResourcesForViewing": {
                "Resources": [
                    {"Url": "/src/html/index.html", "ResourceId": "res1"},
                    {"Url": "/src/css/style.css", "ResourceId": "res2"},
                ]
            },
            "ResourcesMentionedFromViewer": {
                "Resources": [
                    {"Url": "/src/html/index.html", "ResourceId": "res1"},  # 重复
                    {"Url": "/src/js/main.js", "ResourceId": "res3"},
                ]
            },
        }

        # 创建一个资源迭代任务
        task = mock.MagicMock(
            type=TaskType.RESOURCE_ITERATION,
            id=UUID("test-task-id"),
            parameters={"text": "迭代需求", "tags": json.dumps(tags_data)},
        )

        # 模拟IterationAnalyzerCrew
        mock_analyzer = mock.MagicMock()
        mock_crew = mock.MagicMock()
        mock_analyzer.crew.return_value = mock_crew
        mock_crew.kickoff_async = mock.AsyncMock(return_value=mock.MagicMock(raw="分析结果"))

        with mock.patch("src.core.crew_process.IterationAnalyzerCrew", return_value=mock_analyzer):
            # 执行测试
            await self.cm._process_task(task)

            # 验证资源列表中重复资源已被去除
            call_args = mock_crew.kickoff_async.call_args[1]["inputs"]
            self.assertEqual(len(call_args["resource_list"]), 3)  # 应该有3个唯一资源

    async def test_update_cr_task_queue(self):
        """测试_update_cr_task_queue方法的功能"""
        # 模拟需要的方法和对象
        cr_bot_id = UUID("test-cr-bot-id")
        task = self.task1

        # 模拟_get_cm_staff_id方法
        self.cm._get_cm_staff_id = mock.AsyncMock(return_value=UUID("cm-staff-id"))

        # 创建一个模拟的CR进程信息
        opera_id = "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2"
        staff_id = UUID("c1541b83-4ce5-4a68-b492-596982adf71d")
        cr_process = CrewProcessInfo(
            process=mock.MagicMock(),
            bot_id=cr_bot_id,
            crew_config={},
            opera_ids=[UUID(opera_id)],
            roles={opera_id: [[""]]},
            staff_ids={opera_id: [staff_id]},
        )
        self.cm.crew_processes = {cr_bot_id: cr_process}

        # 模拟_SHARED_BOT_TOOL和_SHARED_DIALOGUE_TOOL
        with (
            mock.patch("src.core.crew_process._SHARED_BOT_TOOL") as mock_bot_tool,
            mock.patch("src.core.crew_process._SHARED_DIALOGUE_TOOL") as mock_dialogue_tool,
            mock.patch("src.core.crew_process.asyncio.gather") as mock_gather,
        ):
            # 设置模拟返回值
            mock_bot_tool.run.return_value = {"status": 200}
            mock_dialogue_tool.run.return_value = {"status": 200}
            mock_gather.side_effect = lambda *args: [True, True]  # 模拟两个操作都成功

            # 模拟ApiResponseParser
            with mock.patch("src.core.crew_process.ApiResponseParser") as mock_parser:
                mock_parser.parse_response.return_value = (200, {})

                # 执行测试
                await self.cm._update_cr_task_queue(cr_bot_id, task)

                # 验证_get_cm_staff_id被调用
                self.cm._get_cm_staff_id.assert_called_once_with(task.parameters.get("opera_id"))

                # 验证asyncio.gather被调用
                mock_gather.assert_called_once()

                # 验证gather的参数是两个异步函数的调用结果
                self.assertEqual(len(mock_gather.call_args[0]), 2)

                # 验证_SHARED_BOT_TOOL.run和_SHARED_DIALOGUE_TOOL.run都被调用
                mock_bot_tool.run.assert_called_once()
                mock_dialogue_tool.run.assert_called_once()

                # 验证_SHARED_BOT_TOOL.run的参数
                bot_args = mock_bot_tool.run.call_args[1]
                self.assertEqual(bot_args["action"], "update")
                self.assertEqual(bot_args["bot_id"], cr_bot_id)

                # 验证_SHARED_DIALOGUE_TOOL.run的参数
                dialogue_args = mock_dialogue_tool.run.call_args[1]
                self.assertEqual(dialogue_args["action"], "create")
                self.assertEqual(dialogue_args["opera_id"], task.parameters.get("opera_id"))

                # 验证日志记录
                self.cm.log.info.assert_called_with(f"已成功将任务 {task.id} 分配给CrewRunner {cr_bot_id}")

    async def test_update_cr_task_queue_partial_failure(self):
        """测试_update_cr_task_queue方法处理部分失败的情况"""
        # 模拟需要的方法和对象
        cr_bot_id = UUID("test-cr-bot-id")
        task = self.task1

        # 模拟_get_cm_staff_id方法
        self.cm._get_cm_staff_id = mock.AsyncMock(return_value=UUID("cm-staff-id"))

        # 创建一个模拟的CR进程信息
        opera_id = "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2"
        staff_id = UUID("c1541b83-4ce5-4a68-b492-596982adf71d")
        cr_process = CrewProcessInfo(
            process=mock.MagicMock(),
            bot_id=cr_bot_id,
            crew_config={},
            opera_ids=[UUID(opera_id)],
            roles={opera_id: [[""]]},
            staff_ids={opera_id: [staff_id]},
        )
        self.cm.crew_processes = {cr_bot_id: cr_process}

        # 模拟_SHARED_BOT_TOOL和_SHARED_DIALOGUE_TOOL
        with (
            mock.patch("src.core.crew_process._SHARED_BOT_TOOL") as mock_bot_tool,
            mock.patch("src.core.crew_process._SHARED_DIALOGUE_TOOL") as mock_dialogue_tool,
            mock.patch("src.core.crew_process.asyncio.gather") as mock_gather,
        ):
            # 设置模拟返回值
            mock_bot_tool.run.return_value = {"status": 200}
            mock_dialogue_tool.run.return_value = {"status": 200}
            mock_gather.side_effect = lambda *args: [True, False]  # 模拟一个操作成功，一个失败

            # 模拟ApiResponseParser
            with mock.patch("src.core.crew_process.ApiResponseParser") as mock_parser:
                mock_parser.parse_response.return_value = (200, {})

                # 执行测试
                await self.cm._update_cr_task_queue(cr_bot_id, task)

                # 验证_get_cm_staff_id被调用
                self.cm._get_cm_staff_id.assert_called_once_with(task.parameters.get("opera_id"))

                # 验证asyncio.gather被调用
                mock_gather.assert_called_once()

                # 验证gather的参数是两个异步函数的调用结果
                self.assertEqual(len(mock_gather.call_args[0]), 2)

                # 验证_SHARED_BOT_TOOL.run和_SHARED_DIALOGUE_TOOL.run都被调用
                mock_bot_tool.run.assert_called_once()
                mock_dialogue_tool.run.assert_called_once()

                # 验证日志记录
                self.cm.log.warning.assert_called_with(f"任务 {task.id} 分配给CrewRunner {cr_bot_id} 部分失败")


# 在加载文件时运行测试
if __name__ == "__main__":
    unittest.main()
