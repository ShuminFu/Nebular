import unittest
import json
from unittest.mock import MagicMock, patch
from src.crewai_ext.flows.analysis_flow import AnalysisFlow
from src.core.dialogue.models import ProcessingDialogue
import sys


class TestExtractResourcesFromTags(unittest.TestCase):
    """测试 AnalysisFlow._extract_resources_from_tags 方法"""

    def setUp(self):
        """设置测试环境"""
        # 创建对话模拟对象
        self.mock_dialogue = MagicMock(spec=ProcessingDialogue)
        self.mock_dialogue.mentioned_staff_ids = [{"file_path": "fallback.js", "resource_id": "fallback-id"}]

        # 创建临时对话池模拟对象
        self.mock_pool = MagicMock()

        # 模拟日志对象
        self.mock_logger = MagicMock()

        # 创建 AnalysisFlow 实例
        self.flow = AnalysisFlow(self.mock_dialogue, self.mock_pool)
        # 替换日志对象
        self.flow.log = self.mock_logger

    def test_extract_resources_viewing_format(self):
        """测试从 ResourcesForViewing 格式提取资源"""
        # 准备测试数据
        tags_data = {
            "ResourcesForViewing": {
                "VersionId": "6a737f18-4d82-496f-8f63-5367e897c583",
                "Resources": [
                    {"Url": "/src/js/main.js", "ResourceId": "1679d89d-40d3-4db2-b7f5-a48881d3aa31", "ResourceCacheable": True},
                    {
                        "Url": "/src/css/style.css",
                        "ResourceId": "368e4fd9-e40b-4b18-a48b-1003e71c4aac",
                        "ResourceCacheable": True,
                    },
                ],
                "NavigateIndex": 0,
            }
        }
        tags_str = json.dumps(tags_data)

        # 执行测试
        result = self.flow._extract_resources_from_tags(tags_str)

        # 验证结果
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["file_path"], "/src/js/main.js")  # type: ignore
        self.assertEqual(result[0]["resource_id"], "1679d89d-40d3-4db2-b7f5-a48881d3aa31")  # type: ignore
        self.assertEqual(result[1]["file_path"], "/src/css/style.css")  # type: ignore
        self.assertEqual(result[1]["resource_id"], "368e4fd9-e40b-4b18-a48b-1003e71c4aac")  # type: ignore

    def test_extract_resources_mentioned_format(self):
        """测试从 ResourcesMentionedFromViewer 格式提取资源"""
        # 准备测试数据
        tags_data = {
            "ResourcesMentionedFromViewer": ["473b0612-ee11-43a9-a214-670a3f8cbf4b", "5a1c2b3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d"]
        }
        tags_str = json.dumps(tags_data)

        # 执行测试
        result = self.flow._extract_resources_from_tags(tags_str)

        # 验证结果
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["file_path"], "")  # type: ignore
        self.assertEqual(result[0]["resource_id"], "473b0612-ee11-43a9-a214-670a3f8cbf4b")  # type: ignore
        self.assertEqual(result[1]["file_path"], "")  # type: ignore
        self.assertEqual(result[1]["resource_id"], "5a1c2b3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d")  # type: ignore

    def test_extract_resources_empty_resources(self):
        """测试处理没有资源的情况"""
        # 准备测试数据 - 空的 ResourcesForViewing
        tags_data = {
            "ResourcesForViewing": {"VersionId": "6a737f18-4d82-496f-8f63-5367e897c583", "Resources": [], "NavigateIndex": 0}
        }
        tags_str = json.dumps(tags_data)

        # 执行测试
        result = self.flow._extract_resources_from_tags(tags_str)

        # 验证结果 - 应该返回空列表
        self.assertEqual(result, [])

    def test_extract_resources_invalid_json(self):
        """测试处理无效的 JSON 字符串"""
        # 准备测试数据
        tags_str = "这不是一个有效的JSON字符串"

        # 执行测试
        result = self.flow._extract_resources_from_tags(tags_str)

        # 验证结果 - 应该返回空列表
        self.assertEqual(result, [])

    def test_extract_resources_no_relevant_fields(self):
        """测试处理没有相关字段的 JSON"""
        # 准备测试数据 - 有效的 JSON，但没有相关的资源字段
        tags_data = {"OtherField": "Some value", "AnotherField": 123}
        tags_str = json.dumps(tags_data)

        # 执行测试
        result = self.flow._extract_resources_from_tags(tags_str)

        # 验证结果 - 应该返回空列表
        self.assertEqual(result, [])

    def test_extract_resources_malformed_viewing_structure(self):
        """测试处理结构不完整的 ResourcesForViewing"""
        # 准备测试数据 - ResourcesForViewing 存在但结构不完整
        tags_data = {
            "ResourcesForViewing": {
                "VersionId": "6a737f18-4d82-496f-8f63-5367e897c583",
                # 缺少 Resources 字段
                "NavigateIndex": 0,
            }
        }
        tags_str = json.dumps(tags_data)

        # 执行测试
        result = self.flow._extract_resources_from_tags(tags_str)

        # 验证结果 - 应该返回空列表
        self.assertEqual(result, [])

    def test_extract_resources_malformed_resource_items(self):
        """测试处理资源条目结构不完整的情况"""
        # 准备测试数据 - Resources 中的条目缺少必要字段
        tags_data = {
            "ResourcesForViewing": {
                "VersionId": "6a737f18-4d82-496f-8f63-5367e897c583",
                "Resources": [
                    {
                        # 缺少 Url 字段
                        "ResourceId": "1679d89d-40d3-4db2-b7f5-a48881d3aa31",
                        "ResourceCacheable": True,
                    },
                    {
                        "Url": "/src/css/style.css",
                        # 缺少 ResourceId 字段
                        "ResourceCacheable": True,
                    },
                ],
                "NavigateIndex": 0,
            }
        }
        tags_str = json.dumps(tags_data)

        # 执行测试
        result = self.flow._extract_resources_from_tags(tags_str)

        # 验证结果 - 应该返回空列表，因为没有可提取的完整资源
        self.assertEqual(result, [])

    @patch("src.crewai_ext.flows.analysis_flow.AnalysisFlow._get_resources_by_version_ids")
    def test_extract_resources_selected_texts_format(self, mock_get_resources):
        """测试从 SelectedTextsFromViewer 格式提取资源"""
        # 准备测试数据
        tags_data = {
            "SelectedTextsFromViewer": [
                {"Index": "#1", "SelectedText": "Product Showcase", "VersionId": "96028f82-9f76-4372-976c-f0c5a054db79"},
                {"Index": "#2", "SelectedText": "API Documentation", "VersionId": "a7c52e31-b8d9-4f60-8e15-3d27f9b61c42"},
            ]
        }
        tags_str = json.dumps(tags_data)

        # 设置mock返回值
        expected_resources = [
            {"file_path": "/path/to/showcase.md", "resource_id": "96028f82-9f76-4372-976c-f0c5a054db79"},
            {"file_path": "/path/to/api_docs.md", "resource_id": "a7c52e31-b8d9-4f60-8e15-3d27f9b61c42"},
        ]
        mock_get_resources.return_value = expected_resources

        # 执行测试
        result = self.flow._extract_resources_from_tags(tags_str)

        # 验证结果
        self.assertEqual(result, expected_resources)
        # 验证调用了_get_resources_by_version_ids方法，并传递了正确的参数
        mock_get_resources.assert_called_once_with([
            "96028f82-9f76-4372-976c-f0c5a054db79",
            "a7c52e31-b8d9-4f60-8e15-3d27f9b61c42",
        ])

    @patch("src.crewai_ext.flows.analysis_flow.AnalysisFlow._get_resources_by_version_ids")
    def test_extract_resources_selected_texts_empty_version_id(self, mock_get_resources):
        """测试处理 SelectedTextsFromViewer 中没有 VersionId 的情况"""
        # 准备测试数据 - 缺少 VersionId
        tags_data = {
            "SelectedTextsFromViewer": [
                {
                    "Index": "#1",
                    "SelectedText": "Product Showcase",
                    # 缺少 VersionId
                }
            ]
        }
        tags_str = json.dumps(tags_data)

        # 执行测试
        result = self.flow._extract_resources_from_tags(tags_str)

        # 验证结果 - 应该返回空列表，因为没有可提取的版本ID
        self.assertEqual(result, [])

    def test_extract_resources_mixed_valid_invalid(self):
        """测试处理混合有效和无效资源条目的情况"""
        # 准备测试数据 - 部分资源条目有效，部分无效
        tags_data = {
            "ResourcesForViewing": {
                "VersionId": "6a737f18-4d82-496f-8f63-5367e897c583",
                "Resources": [
                    {
                        # 完整有效的条目
                        "Url": "/src/js/main.js",
                        "ResourceId": "1679d89d-40d3-4db2-b7f5-a48881d3aa31",
                        "ResourceCacheable": True,
                    },
                    {
                        # 缺少 ResourceId 的无效条目
                        "Url": "/src/css/style.css",
                        "ResourceCacheable": True,
                    },
                ],
                "NavigateIndex": 0,
            }
        }
        tags_str = json.dumps(tags_data)

        # 执行测试
        result = self.flow._extract_resources_from_tags(tags_str)

        # 验证结果 - 应该只包含有效的资源条目
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["file_path"], "/src/js/main.js")  # type: ignore
        self.assertEqual(result[0]["resource_id"], "1679d89d-40d3-4db2-b7f5-a48881d3aa31")  # type: ignore

    def test_extract_resources_carriage_return(self):
        """测试处理包含回车符的 JSON 字符串"""
        # 准备测试数据 - 带有回车符的 JSON 字符串
        tags_str = '{\r\n    "ResourcesForViewing": {\r\n        "VersionId": "6a737f18-4d82-496f-8f63-5367e897c583",\r\n        "Resources": [\r\n            {\r\n                "Url": "/src/js/main.js",\r\n                "ResourceId": "1679d89d-40d3-4db2-b7f5-a48881d3aa31",\r\n                "ResourceCacheable": true\r\n            }\r\n        ],\r\n        "NavigateIndex": 0\r\n    }\r\n}'

        # 执行测试
        result = self.flow._extract_resources_from_tags(tags_str)

        # 验证结果
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["file_path"], "/src/js/main.js")  # type: ignore
        self.assertEqual(result[0]["resource_id"], "1679d89d-40d3-4db2-b7f5-a48881d3aa31")  # type: ignore

    def test_extract_resources_current_version_format(self):
        """测试从ResourcesForViewing的CurrentVersion格式提取资源"""
        # 准备测试数据 - CurrentVersion格式
        tags_data = {
            "ResourcesForViewing": {
                "VersionId": "6a737f18-4d82-496f-8f63-5367e897c583",
                "CurrentVersion": {
                    "current_files": [
                        {"file_path": "/src/js/main.js", "resource_id": "1679d89d-40d3-4db2-b7f5-a48881d3aa31"},
                        {"file_path": "/src/css/style.css", "resource_id": "368e4fd9-e40b-4b18-a48b-1003e71c4aac"},
                    ]
                },
            }
        }
        tags_str = json.dumps(tags_data)

        # 执行测试
        result = self.flow._extract_resources_from_tags(tags_str)

        # 验证结果
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["file_path"], "/src/js/main.js")  # type: ignore
        self.assertEqual(result[0]["resource_id"], "1679d89d-40d3-4db2-b7f5-a48881d3aa31")  # type: ignore
        self.assertEqual(result[1]["file_path"], "/src/css/style.css")  # type: ignore
        self.assertEqual(result[1]["resource_id"], "368e4fd9-e40b-4b18-a48b-1003e71c4aac")  # type: ignore

    def test_extract_resources_current_version_modified_files(self):
        """测试从ResourcesForViewing的CurrentVersion格式提取modified_files资源"""
        # 准备测试数据 - CurrentVersion with modified_files格式
        tags_data = {
            "ResourcesForViewing": {
                "VersionId": "6a737f18-4d82-496f-8f63-5367e897c583",
                "CurrentVersion": {
                    "modified_files": [
                        {"file_path": "/src/html/index.html", "resource_id": "18c91231-af74-4704-9960-eff96164428b"},
                        {"file_path": "/src/js/utils.js", "resource_id": "4582a2d7-90c5-4b1e-a7f9-6d21f9e85cb9"},
                    ]
                },
            }
        }
        tags_str = json.dumps(tags_data)

        # 执行测试
        result = self.flow._extract_resources_from_tags(tags_str)

        # 验证结果
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["file_path"], "/src/html/index.html")  # type: ignore
        self.assertEqual(result[0]["resource_id"], "18c91231-af74-4704-9960-eff96164428b")  # type: ignore
        self.assertEqual(result[1]["file_path"], "/src/js/utils.js")  # type: ignore
        self.assertEqual(result[1]["resource_id"], "4582a2d7-90c5-4b1e-a7f9-6d21f9e85cb9")  # type: ignore


class TestGetResourcesByVersionIds(unittest.TestCase):
    """测试 AnalysisFlow._get_resources_by_version_ids 方法"""

    def setUp(self):
        """设置测试环境"""
        # 创建对话模拟对象
        self.mock_dialogue = MagicMock(spec=ProcessingDialogue)
        self.mock_dialogue.opera_id = "test-opera-id"
        self.mock_dialogue.mentioned_staff_ids = [{"file_path": "fallback.js", "resource_id": "fallback-id"}]

        # 创建临时对话池模拟对象
        self.mock_pool = MagicMock()

        # 模拟日志对象
        self.mock_logger = MagicMock()

        # 创建 AnalysisFlow 实例
        self.flow = AnalysisFlow(self.mock_dialogue, self.mock_pool)
        # 替换日志对象
        self.flow.log = self.mock_logger

    @patch("src.crewai_ext.flows.analysis_flow.AnalysisFlow._extract_resources_from_tags")
    def test_get_resources_by_version_id(self, mock_extract_resources):
        """测试通过版本ID获取资源"""
        # 设置版本ID
        version_id = "6a737f18-4d82-496f-8f63-5367e897c583"

        # 模拟对话数据
        mock_dialogue_data = [
            {
                "id": "test-dialogue-id",
                "tags": json.dumps({
                    "ResourcesForViewing": {
                        "VersionId": version_id,
                        "CurrentVersion": {
                            "current_files": [
                                {"file_path": "/src/js/main.js", "resource_id": "1679d89d-40d3-4db2-b7f5-a48881d3aa31"},
                                {"file_path": "/src/css/style.css", "resource_id": "368e4fd9-e40b-4b18-a48b-1003e71c4aac"},
                                {"file_path": "/src/html/index.html", "resource_id": "18c91231-af74-4704-9960-eff96164428b"},
                            ]
                        },
                    }
                }),
            }
        ]

        # 模拟_extract_resources_from_tags方法的返回值
        expected_resources = [
            {"file_path": "/src/js/main.js", "resource_id": "1679d89d-40d3-4db2-b7f5-a48881d3aa31"},
            {"file_path": "/src/css/style.css", "resource_id": "368e4fd9-e40b-4b18-a48b-1003e71c4aac"},
            {"file_path": "/src/html/index.html", "resource_id": "18c91231-af74-4704-9960-eff96164428b"},
        ]
        mock_extract_resources.return_value = expected_resources

        # 模拟DialogueTool类
        mock_dialogue_tool = MagicMock()
        mock_dialogue_tool.run = MagicMock(return_value=json.dumps(mock_dialogue_data))

        # 创建模拟模块
        mock_dialogue_api_tool_module = MagicMock()
        mock_dialogue_api_tool_module.DialogueTool = MagicMock(return_value=mock_dialogue_tool)

        # 将模拟模块临时添加到sys.modules
        with patch.dict(sys.modules, {"crewai_ext.tools.opera_api.dialogue_api_tool": mock_dialogue_api_tool_module}):
            # 执行测试
            result = self.flow._get_resources_by_version_ids([version_id])

        # 验证DialogueTool创建和调用
        mock_dialogue_api_tool_module.DialogueTool.assert_called_once()
        mock_dialogue_tool.run.assert_called_once()

        # 验证_extract_resources_from_tags被调用
        tags_json_str = mock_dialogue_data[0]["tags"]
        mock_extract_resources.assert_called_once_with(tags_json_str)

        # 验证结果
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["file_path"], "/src/js/main.js")  # type: ignore
        self.assertEqual(result[0]["resource_id"], "1679d89d-40d3-4db2-b7f5-a48881d3aa31")  # type: ignore
        self.assertEqual(result[1]["file_path"], "/src/css/style.css")  # type: ignore
        self.assertEqual(result[1]["resource_id"], "368e4fd9-e40b-4b18-a48b-1003e71c4aac")  # type: ignore
        self.assertEqual(result[2]["file_path"], "/src/html/index.html")  # type: ignore
        self.assertEqual(result[2]["resource_id"], "18c91231-af74-4704-9960-eff96164428b")  # type: ignore

    @patch("src.crewai_ext.flows.analysis_flow.AnalysisFlow._extract_resources_from_tags")
    def test_get_resources_by_version_id_modified_files(self, mock_extract_resources):
        """测试通过版本ID获取资源 - 使用modified_files"""
        # 设置版本ID
        version_id = "6a737f18-4d82-496f-8f63-5367e897c583"

        # 模拟API返回的对话数据 - 使用modified_files而非current_files
        mock_dialogue_data = [
            {
                "id": "test-dialogue-id",
                "tags": json.dumps({
                    "ResourcesForViewing": {
                        "VersionId": version_id,
                        "CurrentVersion": {
                            "modified_files": [
                                {"file_path": "/src/js/main.js", "resource_id": "1679d89d-40d3-4db2-b7f5-a48881d3aa31"},
                                {"file_path": "/src/css/style.css", "resource_id": "368e4fd9-e40b-4b18-a48b-1003e71c4aac"},
                            ]
                        },
                    }
                }),
            }
        ]

        # 模拟_extract_resources_from_tags方法的返回值
        expected_resources = [
            {"file_path": "/src/js/main.js", "resource_id": "1679d89d-40d3-4db2-b7f5-a48881d3aa31"},
            {"file_path": "/src/css/style.css", "resource_id": "368e4fd9-e40b-4b18-a48b-1003e71c4aac"},
        ]
        mock_extract_resources.return_value = expected_resources

        # 模拟DialogueTool类
        mock_dialogue_tool = MagicMock()
        mock_dialogue_tool.run = MagicMock(return_value=json.dumps(mock_dialogue_data))

        # 创建模拟模块
        mock_dialogue_api_tool_module = MagicMock()
        mock_dialogue_api_tool_module.DialogueTool = MagicMock(return_value=mock_dialogue_tool)

        # 将模拟模块临时添加到sys.modules
        with patch.dict(sys.modules, {"crewai_ext.tools.opera_api.dialogue_api_tool": mock_dialogue_api_tool_module}):
            # 执行测试
            result = self.flow._get_resources_by_version_ids([version_id])

        # 验证_extract_resources_from_tags被调用
        tags_json_str = mock_dialogue_data[0]["tags"]
        mock_extract_resources.assert_called_once_with(tags_json_str)

        # 验证结果
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["file_path"], "/src/js/main.js")  # type: ignore
        self.assertEqual(result[0]["resource_id"], "1679d89d-40d3-4db2-b7f5-a48881d3aa31")  # type: ignore
        self.assertEqual(result[1]["file_path"], "/src/css/style.css")  # type: ignore
        self.assertEqual(result[1]["resource_id"], "368e4fd9-e40b-4b18-a48b-1003e71c4aac")  # type: ignore

    def test_get_resources_by_version_id_error_handling(self):
        """测试从版本ID获取资源时的错误处理"""
        # 设置版本ID
        version_id = "6a737f18-4d82-496f-8f63-5367e897c583"

        # 模拟DialogueTool类
        mock_dialogue_tool = MagicMock()
        mock_dialogue_tool.run = MagicMock(side_effect=Exception("API调用失败"))

        # 创建模拟模块
        mock_dialogue_api_tool_module = MagicMock()
        mock_dialogue_api_tool_module.DialogueTool = MagicMock(return_value=mock_dialogue_tool)

        # 将模拟模块临时添加到sys.modules
        with patch.dict(sys.modules, {"crewai_ext.tools.opera_api.dialogue_api_tool": mock_dialogue_api_tool_module}):
            # 执行测试
            result = self.flow._get_resources_by_version_ids([version_id])

        # 验证结果 - 应该返回空列表
        self.assertEqual(result, [])
        self.mock_logger.error.assert_called_once()

    @patch("src.crewai_ext.flows.analysis_flow.AnalysisFlow._extract_resources_from_tags")
    def test_get_resources_by_version_id_multiple_versions(self, mock_extract_resources):
        """测试获取多个版本ID的资源并去重"""
        # 设置版本ID
        version_id1 = "6a737f18-4d82-496f-8f63-5367e897c583"
        version_id2 = "7b848f29-5e93-5a83-9f74-6478fa908d94"

        # 模拟API返回的对话数据
        mock_dialogue_data1 = [
            {
                "id": "test-dialogue-id-1",
                "tags": json.dumps({
                    "ResourcesForViewing": {
                        "VersionId": version_id1,
                        "CurrentVersion": {
                            "current_files": [
                                {"file_path": "/src/js/main.js", "resource_id": "1679d89d-40d3-4db2-b7f5-a48881d3aa31"},
                                {"file_path": "/src/css/style.css", "resource_id": "368e4fd9-e40b-4b18-a48b-1003e71c4aac"},
                            ]
                        },
                    }
                }),
            }
        ]

        mock_dialogue_data2 = [
            {
                "id": "test-dialogue-id-2",
                "tags": json.dumps({
                    "ResourcesForViewing": {
                        "VersionId": version_id2,
                        "CurrentVersion": {
                            "current_files": [
                                {
                                    "file_path": "/src/js/main.js",
                                    "resource_id": "1679d89d-40d3-4db2-b7f5-a48881d3aa31",
                                },  # 重复资源
                                {
                                    "file_path": "/src/html/index.html",
                                    "resource_id": "18c91231-af74-4704-9960-eff96164428b",
                                },  # 新资源
                            ]
                        },
                    }
                }),
            }
        ]

        # 模拟_extract_resources_from_tags方法的返回值
        mock_extract_resources.side_effect = [
            [  # 第一次调用的返回值
                {"file_path": "/src/js/main.js", "resource_id": "1679d89d-40d3-4db2-b7f5-a48881d3aa31"},
                {"file_path": "/src/css/style.css", "resource_id": "368e4fd9-e40b-4b18-a48b-1003e71c4aac"},
            ],
            [  # 第二次调用的返回值
                {"file_path": "/src/js/main.js", "resource_id": "1679d89d-40d3-4db2-b7f5-a48881d3aa31"},  # 重复资源
                {"file_path": "/src/html/index.html", "resource_id": "18c91231-af74-4704-9960-eff96164428b"},  # 新资源
            ],
        ]

        # 模拟DialogueTool类
        mock_dialogue_tool = MagicMock()
        mock_dialogue_tool.run = MagicMock(side_effect=[json.dumps(mock_dialogue_data1), json.dumps(mock_dialogue_data2)])

        # 创建模拟模块
        mock_dialogue_api_tool_module = MagicMock()
        mock_dialogue_api_tool_module.DialogueTool = MagicMock(return_value=mock_dialogue_tool)

        # 将模拟模块临时添加到sys.modules
        with patch.dict(sys.modules, {"crewai_ext.tools.opera_api.dialogue_api_tool": mock_dialogue_api_tool_module}):
            # 执行测试
            result = self.flow._get_resources_by_version_ids([version_id1, version_id2])

        # 验证_extract_resources_from_tags被调用了两次
        self.assertEqual(mock_extract_resources.call_count, 2)
        # 验证第一次调用的参数
        mock_extract_resources.assert_any_call(mock_dialogue_data1[0]["tags"])
        # 验证第二次调用的参数
        mock_extract_resources.assert_any_call(mock_dialogue_data2[0]["tags"])

        # 验证结果 - 应该有3个不重复的资源
        self.assertEqual(len(result), 3)
        # 验证资源ID是否正确
        resource_ids = [r["resource_id"] for r in result]  # type: ignore
        self.assertIn("1679d89d-40d3-4db2-b7f5-a48881d3aa31", resource_ids)
        self.assertIn("368e4fd9-e40b-4b18-a48b-1003e71c4aac", resource_ids)
        self.assertIn("18c91231-af74-4704-9960-eff96164428b", resource_ids)


if __name__ == "__main__":
    unittest.main()
