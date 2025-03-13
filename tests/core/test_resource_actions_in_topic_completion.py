import unittest
from unittest import mock
import json
from uuid import UUID
from datetime import datetime, timezone
import pytest

from src.core.crew_bots.crew_manager import CrewManager
from src.core.task_utils import BotTask, TaskType, TaskStatus, TaskPriority
from src.core.topic.topic_tracker import TopicInfo, VersionMeta


class TestResourceActionsInTopicCompletion(unittest.TestCase):
    """测试主题完成时不同资源状态（不变的、更新的和删除的文件）的处理"""

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

        # 使用用户提供的示例创建VersionMeta
        # 模拟主题完成后的状态
        self.version_meta = VersionMeta(
            parent_version="6a737f18-4d82-496f-8f63-5367e897c583",
            modified_files=[
                {"file_path": "/src/html/index.html", "resource_id": "a24131a5-a488-4583-85de-1e13288cab4a"},
            ],
            description="删除 JS 资源文件，因为该迭代任务要求移除所有 JS 文件。",
            current_files=[
                {"file_path": "/src/html/index.html", "resource_id": "a24131a5-a488-4583-85de-1e13288cab4a"},
            ],
            deleted_files=[
                {"file_path": "/src/js/main.js", "resource_id": "1679d89d-40d3-4db2-b7f5-a48881d3aa31"},
                {"file_path": "/src/css/style.css", "resource_id": "368e4fd9-e40b-4b18-a48b-1003e71c4aac"},
            ],
        )

        # 创建与用户示例匹配的TopicInfo
        self.topic_info = TopicInfo(
            tasks={
                UUID("227390d2-ce3e-477d-a5c4-d76f94134716"),
                UUID("18e1b45a-4831-4925-9947-0f8bf0bb406e"),
                UUID("d0fee6df-8148-4f61-8c7c-22435af4580b"),
                UUID("0ddf0a05-30b8-4054-864a-79cd67e1e00e"),
            },
            type="CODE_RESOURCE",
            status="active",
            opera_id="99a51bfa-0b95-46e5-96b3-e3cfc021a6b2",
            current_version=self.version_meta,
            expected_creation_count=1,
            actual_creation_count=1,
            completed_creation_count=1,
        )

        # 模拟任务对象
        self.completed_tasks = [
            # HTML文件更新任务
            BotTask(
                id=UUID("227390d2-ce3e-477d-a5c4-d76f94134716"),
                created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
                completed_at=datetime(2023, 1, 1, 1, tzinfo=timezone.utc),
                priority=TaskPriority.NORMAL,
                type=TaskType.RESOURCE_CREATION,
                status=TaskStatus.COMPLETED,
                description="更新HTML文件",
                parameters={
                    "file_path": "/src/html/index.html",
                    "opera_id": "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2",
                    "action": "update",
                },
                topic_id="test-topic-resource-changes",
                result={"resource_id": "a24131a5-a488-4583-85de-1e13288cab4a"},
            ),
            # JS文件删除任务
            BotTask(
                id=UUID("18e1b45a-4831-4925-9947-0f8bf0bb406e"),
                created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
                completed_at=datetime(2023, 1, 1, 2, tzinfo=timezone.utc),
                priority=TaskPriority.NORMAL,
                type=TaskType.RESOURCE_GENERATION,
                status=TaskStatus.COMPLETED,
                description="删除JS文件",
                parameters={
                    "file_path": "/src/js/main.js",
                    "opera_id": "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2",
                    "action": "delete",
                    "resource_id": "1679d89d-40d3-4db2-b7f5-a48881d3aa31",
                },
                topic_id="test-topic-resource-changes",
            ),
            # CSS文件删除任务
            BotTask(
                id=UUID("d0fee6df-8148-4f61-8c7c-22435af4580b"),
                created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
                completed_at=datetime(2023, 1, 1, 3, tzinfo=timezone.utc),
                priority=TaskPriority.NORMAL,
                type=TaskType.RESOURCE_GENERATION,
                status=TaskStatus.COMPLETED,
                description="删除CSS文件",
                parameters={
                    "file_path": "/src/css/style.css",
                    "opera_id": "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2",
                    "action": "delete",
                    "resource_id": "368e4fd9-e40b-4b18-a48b-1003e71c4aac",
                },
                topic_id="test-topic-resource-changes",
            ),
        ]

        # 设置TopicTracker模拟
        self.cm.topic_tracker = mock.MagicMock()
        self.cm.topic_tracker.get_topic_info.return_value = self.topic_info
        self.cm.topic_tracker._completed_tasks = {
            "test-topic-resource-changes": {
                UUID("227390d2-ce3e-477d-a5c4-d76f94134716"),
                UUID("18e1b45a-4831-4925-9947-0f8bf0bb406e"),
                UUID("d0fee6df-8148-4f61-8c7c-22435af4580b"),
                UUID("0ddf0a05-30b8-4054-864a-79cd67e1e00e"),
            }
        }

        # 设置task_queue.tasks
        self.cm.task_queue.tasks = self.completed_tasks

    def tearDown(self):
        """清理测试环境"""
        mock.patch.stopall()

    @pytest.mark.asyncio
    @mock.patch("src.core.crew_process.DialogueForCreation")
    async def test_handle_topic_completed_with_mixed_resource_actions(self, mock_dialogue_creation):
        """测试主题完成时处理混合资源操作（更新和删除）"""
        # 调用被测试的方法
        await self.cm._handle_topic_completed("test-topic-resource-changes", "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2")

        # 验证_get_cm_staff_id被调用
        self.cm._get_cm_staff_id.assert_called_once_with("99a51bfa-0b95-46e5-96b3-e3cfc021a6b2")

        # 验证get_topic_info被调用
        self.cm.topic_tracker.get_topic_info.assert_called_once_with("test-topic-resource-changes")

        # 验证对话创建
        mock_dialogue_creation.assert_called_once()
        dialogue_args = mock_dialogue_creation.call_args[1]
        self.assertEqual(dialogue_args["staff_id"], str(UUID("11111111-1111-1111-1111-111111111111")))
        self.assertEqual(dialogue_args["text"], "主题 test-topic-resource-changes 的所有资源已生成完成。")

        # 验证资源标签
        resources_tag = json.loads(dialogue_args["tags"])

        # 1. 验证ResourcesForViewing基本结构
        self.assertEqual(resources_tag["ResourcesForViewing"]["VersionId"], "test-topic-resource-changes")

        # 2. 验证Resources列表只包含修改过的文件（这里是HTML文件）
        resources = resources_tag["ResourcesForViewing"]["Resources"]
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["Url"], "/src/html/index.html")
        self.assertEqual(resources[0]["ResourceId"], "a24131a5-a488-4583-85de-1e13288cab4a")
        self.assertTrue(resources[0]["ResourceCacheable"])

        # 3. 验证CurrentVersion信息
        current_version = resources_tag["ResourcesForViewing"]["CurrentVersion"]
        self.assertEqual(current_version["parent_version"], "6a737f18-4d82-496f-8f63-5367e897c583")
        self.assertEqual(current_version["description"], "删除 JS 资源文件，因为该迭代任务要求移除所有 JS 文件。")

        # 4. 验证当前文件列表
        self.assertEqual(len(current_version["current_files"]), 1)
        self.assertEqual(current_version["current_files"][0]["file_path"], "/src/html/index.html")
        self.assertEqual(current_version["current_files"][0]["resource_id"], "a24131a5-a488-4583-85de-1e13288cab4a")

        # 5. 验证修改的文件列表
        self.assertEqual(len(current_version["modified_files"]), 1)
        self.assertEqual(current_version["modified_files"][0]["file_path"], "/src/html/index.html")
        self.assertEqual(current_version["modified_files"][0]["resource_id"], "a24131a5-a488-4583-85de-1e13288cab4a")

        # 6. 验证删除的文件路径
        self.assertTrue("RemovingResources" in resources_tag)
        removing_resources = resources_tag["RemovingResources"]
        self.assertEqual(len(removing_resources), 2)
        self.assertIn("/src/js/main.js", removing_resources)
        self.assertIn("/src/css/style.css", removing_resources)

        # 7. 验证导航索引
        self.assertEqual(resources_tag["ResourcesForViewing"]["NavigateIndex"], 0)

        # 验证_SHARED_DIALOGUE_TOOL.run被调用
        self.mock_dialogue_tool.run.assert_called_once()

        # 验证日志记录
        self.cm.log.info.assert_called_with("已发送主题 test-topic-resource-changes 完成对话，包含 1 个资源")

    def test_build_resource_list_from_version_with_mixed_actions(self):
        """测试从包含不同操作的版本构建资源列表"""
        # 调用被测试的方法
        resources = self.cm._build_resource_list_from_version(self.version_meta)

        # 验证资源列表
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["Url"], "/src/html/index.html")
        self.assertEqual(resources[0]["ResourceId"], "a24131a5-a488-4583-85de-1e13288cab4a")
        self.assertTrue(resources[0]["ResourceCacheable"])
