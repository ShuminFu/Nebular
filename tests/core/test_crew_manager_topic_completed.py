import unittest
from unittest import mock
import json
from uuid import UUID
from datetime import datetime, timezone, timedelta

from src.core.crew_process import CrewManager
from src.core.task_utils import BotTask, TaskType, TaskStatus, TaskPriority
from src.core.topic.topic_tracker import TopicInfo, VersionMeta


class TestCrewManagerTopicCompleted(unittest.TestCase):
    """测试CrewManager处理主题完成相关的方法"""

    def setUp(self):
        """设置测试环境和模拟数据"""
        # 创建CrewManager实例并模拟其依赖项
        self.cm = CrewManager()
        self.cm.log = mock.MagicMock()
        self.cm.task_queue = mock.MagicMock()

        # 模拟_get_cm_staff_id方法
        self.cm._get_cm_staff_id = mock.AsyncMock(return_value=UUID("11111111-1111-1111-1111-111111111111"))

        # 模拟_SHARED_DIALOGUE_TOOL
        self.mock_dialogue_tool = mock.patch("src.core.crew_process._SHARED_DIALOGUE_TOOL").start()
        self.mock_dialogue_tool.run.return_value = {"code": 200}

        # 模拟ApiResponseParser
        self.mock_parser = mock.patch("src.core.crew_process.ApiResponseParser").start()
        self.mock_parser.parse_response.return_value = (200, {})

        # 创建TopicInfo和VersionMeta示例
        self.version_meta = VersionMeta(
            parent_version="0",
            modified_files=[
                {"file_path": "/src/html/index.html", "resource_id": "res-001"},
                {"file_path": "/src/css/style.css", "resource_id": "res-002"},
                {"file_path": "/src/js/main.js", "resource_id": "res-003"},
            ],
            description="测试版本",
            current_files=[
                {"file_path": "/src/html/index.html", "resource_id": "res-001"},
                {"file_path": "/src/css/style.css", "resource_id": "res-002"},
                {"file_path": "/src/js/main.js", "resource_id": "res-003"},
            ],
        )

        self.topic_info = TopicInfo(
            tasks={
                UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
                UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            },
            type="CODE_RESOURCE",
            status="active",
            opera_id="99a51bfa-0b95-46e5-96b3-e3cfc021a6b2",
            current_version=self.version_meta,
        )

        # 创建任务示例
        self.completed_tasks = [
            BotTask(
                id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
                completed_at=datetime(2023, 1, 1, 1, tzinfo=timezone.utc),
                priority=TaskPriority.NORMAL,
                type=TaskType.RESOURCE_CREATION,
                status=TaskStatus.COMPLETED,
                description="创建HTML文件",
                parameters={"file_path": "/src/html/index.html", "opera_id": "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2"},
                topic_id="topic-001",
                result={"resource_id": "res-001"},
            ),
            BotTask(
                id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
                created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
                completed_at=datetime(2023, 1, 1, 2, tzinfo=timezone.utc),
                priority=TaskPriority.NORMAL,
                type=TaskType.RESOURCE_CREATION,
                status=TaskStatus.COMPLETED,
                description="创建CSS文件",
                parameters={"file_path": "/src/css/style.css", "opera_id": "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2"},
                topic_id="topic-001",
                result={"resource_id": "res-002"},
            ),
            BotTask(
                id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
                created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
                completed_at=datetime(2023, 1, 1, 3, tzinfo=timezone.utc),
                priority=TaskPriority.NORMAL,
                type=TaskType.RESOURCE_CREATION,
                status=TaskStatus.COMPLETED,
                description="创建JS文件",
                parameters={"file_path": "/src/js/main.js", "opera_id": "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2"},
                topic_id="topic-001",
                result={"resource_id": "res-003"},
            ),
        ]

        # 设置TopicTracker模拟
        self.cm.topic_tracker = mock.MagicMock()
        self.cm.topic_tracker.get_topic_info.return_value = self.topic_info
        self.cm.topic_tracker._completed_tasks = {
            "topic-001": {
                UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
                UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            }
        }

        # 设置task_queue.tasks
        self.cm.task_queue.tasks = self.completed_tasks

    def tearDown(self):
        """清理测试环境"""
        mock.patch.stopall()

    @mock.patch("src.core.crew_process.DialogueForCreation")
    async def test_handle_topic_completed_with_version(self, mock_dialogue_creation):
        """测试当主题有完整版本信息时的_handle_topic_completed方法"""
        # 设置返回的主题信息
        self.cm.topic_tracker.get_topic_info.return_value = self.topic_info

        # 调用被测试的方法
        await self.cm._handle_topic_completed("topic-001", "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2")

        # 验证_get_cm_staff_id被调用
        self.cm._get_cm_staff_id.assert_called_once_with("99a51bfa-0b95-46e5-96b3-e3cfc021a6b2")

        # 验证get_topic_info被调用
        self.cm.topic_tracker.get_topic_info.assert_called_once_with("topic-001")

        # 验证对话创建
        mock_dialogue_creation.assert_called_once()
        dialogue_args = mock_dialogue_creation.call_args[1]
        self.assertEqual(dialogue_args["staff_id"], str(UUID("11111111-1111-1111-1111-111111111111")))
        self.assertEqual(dialogue_args["text"], "主题 topic-001 的所有资源已生成完成。")

        # 验证资源标签
        resources_tag = json.loads(dialogue_args["tags"])
        self.assertEqual(resources_tag["ResourcesForViewing"]["VersionId"], "topic-001")
        self.assertEqual(len(resources_tag["ResourcesForViewing"]["Resources"]), 3)

        # 验证导航索引
        self.assertEqual(resources_tag["ResourcesForViewing"]["NavigateIndex"], 0)

        # 验证_SHARED_DIALOGUE_TOOL.run被调用
        self.mock_dialogue_tool.run.assert_called_once()

        # 验证日志记录
        self.cm.log.info.assert_called_with("已发送主题 topic-001 完成对话，包含 3 个资源")

    @mock.patch("src.core.crew_process.DialogueForCreation")
    async def test_handle_topic_completed_with_null_current_version(self, mock_dialogue_creation):
        """测试当主题current_version为None时的_handle_topic_completed方法"""
        # 修改主题信息，设置current_version为None
        topic_info = TopicInfo(
            tasks=self.topic_info.tasks,
            type=self.topic_info.type,
            status=self.topic_info.status,
            opera_id=self.topic_info.opera_id,
            current_version=None,
        )
        self.cm.topic_tracker.get_topic_info.return_value = topic_info

        # 调用被测试的方法
        await self.cm._handle_topic_completed("topic-001", "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2")

        # 验证已创建默认版本
        self.assertIsNotNone(topic_info.current_version)
        self.assertEqual(topic_info.current_version.description, "Auto-initialized on completion")

        # 验证对话创建
        mock_dialogue_creation.assert_called_once()
        dialogue_args = mock_dialogue_creation.call_args[1]

        # 验证资源标签
        resources_tag = json.loads(dialogue_args["tags"])
        self.assertEqual(resources_tag["ResourcesForViewing"]["VersionId"], "topic-001")
        # 因为是空版本，所以应该没有资源
        self.assertEqual(len(resources_tag["ResourcesForViewing"]["Resources"]), 0)

    @mock.patch("src.core.crew_process.DialogueForCreation")
    async def test_handle_topic_completed_with_no_topic_info(self, mock_dialogue_creation):
        """测试当找不到主题信息时的_handle_topic_completed方法"""
        # 设置返回None的主题信息
        self.cm.topic_tracker.get_topic_info.return_value = None

        # 调用被测试的方法
        await self.cm._handle_topic_completed("topic-001", "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2")

        # 验证记录了错误日志
        self.cm.log.error.assert_called_with("找不到主题 topic-001 的信息")

        # 验证对话未创建
        mock_dialogue_creation.assert_not_called()

    @mock.patch("src.core.crew_process.DialogueForCreation")
    async def test_handle_topic_completed_with_staff_id_error(self, mock_dialogue_creation):
        """测试当获取staff_id失败时的_handle_topic_completed方法"""
        # 设置_get_cm_staff_id返回None
        self.cm._get_cm_staff_id.return_value = None

        # 调用被测试的方法
        await self.cm._handle_topic_completed("topic-001", "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2")

        # 验证记录了错误日志
        self.cm.log.error.assert_called_with("无法为主题 topic-001 创建总结任务：无法获取CM的staff_id")

        # 验证对话未创建
        mock_dialogue_creation.assert_not_called()

    def test_build_resource_list_from_version(self):
        """测试_build_resource_list_from_version方法"""
        # 调用被测试的方法
        resources, html_files = self.cm._build_resource_list_from_version(self.version_meta)

        # 验证资源列表正确
        self.assertEqual(len(resources), 3)
        self.assertEqual(resources[0]["Url"], "/src/html/index.html")
        self.assertEqual(resources[0]["ResourceId"], "res-001")
        self.assertTrue(resources[0]["ResourceCacheable"])

        # 验证HTML文件列表正确
        self.assertEqual(len(html_files), 1)
        self.assertEqual(html_files[0], "/src/html/index.html")

    def test_add_navigation_index_if_needed_with_index_html(self):
        """测试当存在index.html文件时_add_navigation_index_if_needed方法"""
        # 准备测试数据
        html_files = ["/src/html/about.html", "/src/html/index.html", "/src/html/contact.html"]
        resources_tag = {"ResourcesForViewing": {}}

        # 调用被测试的方法
        self.cm._add_navigation_index_if_needed(resources_tag, html_files)

        # 验证NavigateIndex被设置为index.html的位置
        self.assertEqual(resources_tag["ResourcesForViewing"]["NavigateIndex"], 1)

    def test_add_navigation_index_if_needed_without_index_html(self):
        """测试当不存在index.html文件时_add_navigation_index_if_needed方法"""
        # 准备测试数据
        html_files = ["/src/html/about.html", "/src/html/contact.html"]
        resources_tag = {"ResourcesForViewing": {}}

        # 调用被测试的方法
        self.cm._add_navigation_index_if_needed(resources_tag, html_files)

        # 验证NavigateIndex未设置
        self.assertNotIn("NavigateIndex", resources_tag["ResourcesForViewing"])

    def test_add_navigation_index_if_needed_with_empty_html_files(self):
        """测试当HTML文件列表为空时_add_navigation_index_if_needed方法"""
        # 准备测试数据
        html_files = []
        resources_tag = {"ResourcesForViewing": {}}

        # 调用被测试的方法
        self.cm._add_navigation_index_if_needed(resources_tag, html_files)

        # 验证NavigateIndex未设置
        self.assertNotIn("NavigateIndex", resources_tag["ResourcesForViewing"])

    @mock.patch("src.core.crew_process.DialogueForCreation")
    async def test_handle_topic_completed_fallback_to_task_scan(self, mock_dialogue_creation):
        """测试当current_files为空时回退到遍历任务的情况"""
        # 修改主题信息，设置current_files为空
        empty_version = VersionMeta(
            parent_version="0",
            modified_files=[],
            description="测试版本",
            current_files=[],  # 空的文件列表
        )
        topic_info = TopicInfo(
            tasks=self.topic_info.tasks,
            type=self.topic_info.type,
            status=self.topic_info.status,
            opera_id=self.topic_info.opera_id,
            current_version=empty_version,
        )
        self.cm.topic_tracker.get_topic_info.return_value = topic_info

        # 调用被测试的方法
        await self.cm._handle_topic_completed("topic-001", "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2")

        # 验证记录了警告日志
        self.cm.log.warning.assert_any_call("主题 topic-001 的current_files为空，回退到遍历方式")

        # 验证对话创建
        mock_dialogue_creation.assert_called_once()
        dialogue_args = mock_dialogue_creation.call_args[1]

        # 验证资源标签 - 应该从任务中收集到三个资源
        resources_tag = json.loads(dialogue_args["tags"])
        self.assertEqual(len(resources_tag["ResourcesForViewing"]["Resources"]), 3)  # 通过任务找到3个资源

        # 验证NavigateIndex应该被设置，因为有index.html文件
        self.assertEqual(resources_tag["ResourcesForViewing"]["NavigateIndex"], 0)

    def test_build_resource_list_from_tasks(self):
        """测试_build_resource_list_from_tasks方法"""
        # 调用被测试的方法
        task_dict = {
            "/src/html/index.html": self.completed_tasks[0],
            "/src/css/style.css": self.completed_tasks[1],
            "/src/js/main.js": self.completed_tasks[2],
        }

        resources, html_files = self.cm._build_resource_list_from_tasks(task_dict.values())

        # 验证资源列表正确
        self.assertEqual(len(resources), 3)
        for resource in resources:
            self.assertIn(resource["Url"], ["/src/html/index.html", "/src/css/style.css", "/src/js/main.js"])
            self.assertIn(resource["ResourceId"], ["res-001", "res-002", "res-003"])
            self.assertTrue(resource["ResourceCacheable"])

        # 验证HTML文件列表正确
        self.assertEqual(len(html_files), 1)
        self.assertEqual(html_files[0], "/src/html/index.html")

    def test_build_resource_list_from_tasks_empty(self):
        """测试_build_resource_list_from_tasks方法处理空任务列表"""
        # 调用被测试的方法处理空列表
        resources, html_files = self.cm._build_resource_list_from_tasks([])

        # 验证结果为空
        self.assertEqual(len(resources), 0)
        self.assertEqual(len(html_files), 0)

    def test_build_resource_list_from_tasks_incomplete_data(self):
        """测试_build_resource_list_from_tasks方法处理不完整的任务数据"""
        # 创建缺少file_path的任务
        task_without_path = BotTask(
            id=UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            completed_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            priority=TaskPriority.NORMAL,
            type=TaskType.RESOURCE_CREATION,
            status=TaskStatus.COMPLETED,
            description="创建缺少路径的文件",
            parameters={},  # 没有file_path
            topic_id="topic-001",
            result={"resource_id": "res-004"},
        )

        # 创建缺少resource_id的任务
        task_without_resource_id = BotTask(
            id=UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            completed_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            priority=TaskPriority.NORMAL,
            type=TaskType.RESOURCE_CREATION,
            status=TaskStatus.COMPLETED,
            description="创建缺少资源ID的文件",
            parameters={"file_path": "/src/data/data.json"},
            topic_id="topic-001",
            result={},  # 没有resource_id
        )

        # 调用被测试的方法处理不完整的任务数据
        tasks = [task_without_path, task_without_resource_id, self.completed_tasks[0]]
        resources, html_files = self.cm._build_resource_list_from_tasks(tasks)

        # 验证只有完整的任务被添加到资源列表
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["Url"], "/src/html/index.html")
        self.assertEqual(resources[0]["ResourceId"], "res-001")


if __name__ == "__main__":
    unittest.main()
