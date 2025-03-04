import unittest
import asyncio
import json
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4, UUID

from src.core.dialogue.models import ProcessingDialogue, IntentAnalysis
from src.core.dialogue.pools import DialoguePool
from src.core.dialogue.enums import DialogueType, ProcessingStatus
from src.opera_service.signalr_client.opera_signalr_client import MessageReceivedArgs
from src.core.crew_process import BaseCrewProcess
from src.crewai_ext.flows.analysis_flow import AnalysisFlow


class TestFullAnalysisFlow(unittest.TestCase):
    """测试完整的分析流程，包括从消息处理到AnalysisFlow的全流程"""

    def setUp(self):
        """设置测试环境"""
        # 创建一个带ResourcesForViewing标签的消息
        self.tags_data = {
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
        self.tags_str = json.dumps(self.tags_data)

        # 创建一个测试消息
        self.opera_id = uuid4()
        self.sender_staff_id = uuid4()
        self.receiver_staff_id = uuid4()

        # 创建MessageReceivedArgs对象
        self.message_args = MagicMock(spec=MessageReceivedArgs)
        self.message_args.index = 1
        self.message_args.opera_id = self.opera_id
        self.message_args.sender_staff_id = self.sender_staff_id
        self.message_args.text = "请查看这些资源"
        self.message_args.tags = self.tags_str
        self.message_args.mentioned_staff_ids = [self.receiver_staff_id]

        # 创建对话池
        self.dialogue_pool = MagicMock(spec=DialoguePool)

        # 设置BaseCrewProcess的模拟实例
        self.mock_crew_process = MagicMock(spec=BaseCrewProcess)
        self.mock_crew_process.dialogue_pool = self.dialogue_pool

        # 创建意图处理器模拟
        self.mock_intent_processor = AsyncMock()
        self.mock_crew_process.intent_processor = self.mock_intent_processor

        # 设置日志模拟
        self.mock_logger = MagicMock()

        # 激活的对话和分析流程实例将在测试中创建

    @patch("src.core.dialogue.models.ProcessingDialogue.from_message_args")
    @patch("src.crewai_ext.flows.analysis_flow.AnalysisFlow")
    async def test_full_analysis_flow(self, mock_analysis_flow_class, mock_from_message_args):
        """测试完整的分析流程

        1. 模拟收到带ResourcesForViewing标签的消息
        2. 处理消息并创建ProcessingDialogue对象
        3. 创建AnalysisFlow并执行分析流程
        4. 验证从对话中正确提取了资源
        """
        # 设置ProcessingDialogue.from_message_args的返回值
        dialogue = ProcessingDialogue(
            dialogue_index=1,
            opera_id=self.opera_id,
            sender_staff_id=self.sender_staff_id,
            receiver_staff_ids=[self.receiver_staff_id],
            text_content="请查看这些资源",
            tags=self.tags_str,
            mentioned_staff_ids=[self.receiver_staff_id],
            type=DialogueType.NORMAL,
        )
        mock_from_message_args.return_value = dialogue

        # 设置AnalysisFlow实例
        mock_analysis_flow = AsyncMock()
        mock_analysis_flow_class.return_value = mock_analysis_flow

        # 设置_extract_resources_from_tags方法的实际调用
        analysis_flow_instance = AnalysisFlow(dialogue, self.dialogue_pool)
        analysis_flow_instance.log = self.mock_logger

        # 打补丁使mock_analysis_flow._extract_resources_from_tags使用真实方法
        mock_analysis_flow._extract_resources_from_tags = analysis_flow_instance._extract_resources_from_tags

        # 模拟意图分析结果
        intent_analysis = IntentAnalysis(intent="view_resources", confidence=0.95, parameters={})
        dialogue.intent_analysis = intent_analysis
        dialogue.status = ProcessingStatus.INTENT_ANALYZED

        # 执行测试 - 模拟BaseCrewProcess._handle_message
        await self._simulate_handle_message()

        # 验证意图处理器被调用
        self.mock_intent_processor.process_message.assert_called_once_with(self.message_args)

        # 验证分析流程被创建和启动
        mock_analysis_flow_class.assert_called_once()
        mock_analysis_flow.start_method.assert_called_once()

        # 验证资源提取
        resources = analysis_flow_instance._extract_resources_from_tags(self.tags_str)
        self.assertEqual(len(resources), 2)
        self.assertEqual(resources[0]["Url"], "/src/js/main.js")
        self.assertEqual(resources[0]["ResourceId"], "1679d89d-40d3-4db2-b7f5-a48881d3aa31")
        self.assertEqual(resources[1]["Url"], "/src/css/style.css")

    async def _simulate_handle_message(self):
        """模拟BaseCrewProcess._handle_message方法的行为"""
        # 创建ProcessingDialogue对象
        dialogue = ProcessingDialogue.from_message_args(self.message_args, dialogue_type=DialogueType.NORMAL)

        # 调用意图处理器处理消息
        await self.mock_intent_processor.process_message(self.message_args)

        # 创建分析流程并执行
        analysis_flow = AnalysisFlow(dialogue, self.dialogue_pool)
        await analysis_flow.start_method()

        return dialogue, analysis_flow

    def test_extract_resources_viewing_format(self):
        """测试从ResourcesForViewing格式提取资源的功能"""
        # 创建对话和分析流程
        dialogue = ProcessingDialogue(
            dialogue_index=1,
            opera_id=self.opera_id,
            sender_staff_id=self.sender_staff_id,
            receiver_staff_ids=[self.receiver_staff_id],
            text_content="请查看这些资源",
            tags=self.tags_str,
            mentioned_staff_ids=[self.receiver_staff_id],
            type=DialogueType.NORMAL,
        )
        flow = AnalysisFlow(dialogue, self.dialogue_pool)
        flow.log = self.mock_logger

        # 执行资源提取
        result = flow._extract_resources_from_tags(self.tags_str)

        # 验证结果
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["Url"], "/src/js/main.js")
        self.assertEqual(result[0]["ResourceId"], "1679d89d-40d3-4db2-b7f5-a48881d3aa31")
        self.assertEqual(result[1]["Url"], "/src/css/style.css")
        self.assertEqual(result[1]["ResourceId"], "368e4fd9-e40b-4b18-a48b-1003e71c4aac")

    @patch("src.crewai_ext.flows.analysis_flow.AnalysisFlow._get_resources_by_version_ids")
    def test_debug_flow_step_by_step(self, mock_get_resources):
        """测试逐步调试分析流程

        设置断点的建议位置:
        1. src/core/crew_process.py中的_handle_message方法
        2. src/crewai_ext/flows/analysis_flow.py中的start_method
        3. src/crewai_ext/flows/analysis_flow.py中的_extract_resources_from_tags方法
        4. src/crewai_ext/flows/analysis_flow.py中的analyze_intent方法
        """
        # 准备测试数据 - 同上
        dialogue = ProcessingDialogue(
            dialogue_index=1,
            opera_id=self.opera_id,
            sender_staff_id=self.sender_staff_id,
            receiver_staff_ids=[self.receiver_staff_id],
            text_content="请查看这些资源",
            tags=self.tags_str,
            mentioned_staff_ids=[self.receiver_staff_id],
            type=DialogueType.NORMAL,
        )

        # 模拟_get_resources_by_version_ids返回结果
        mock_get_resources.return_value = [
            {"Url": "/src/js/main.js", "ResourceId": "1679d89d-40d3-4db2-b7f5-a48881d3aa31", "Content": "console.log('Hello')"},
            {
                "Url": "/src/css/style.css",
                "ResourceId": "368e4fd9-e40b-4b18-a48b-1003e71c4aac",
                "Content": "body { color: red; }",
            },
        ]

        # 创建AnalysisFlow实例以供调试
        flow = AnalysisFlow(dialogue, self.dialogue_pool)
        flow.log = self.mock_logger

        # 断点建议: 在这里设置断点，然后逐步执行
        resources = flow._extract_resources_from_tags(dialogue.tags)

        # 验证结果
        self.assertEqual(len(resources), 2)

        # 模拟调用analyze_intent (实际使用时应设置断点)
        intent_analysis = IntentAnalysis(intent="view_resources", confidence=0.95, parameters={})
        dialogue.intent_analysis = intent_analysis

        # 这里故意不执行异步方法，因为这是同步测试
        # 实际调试时，应该使用异步运行器并在相关方法处设置断点

        # 验证数据结构
        self.assertEqual(dialogue.intent_analysis.intent, "view_resources")
        self.assertEqual(dialogue.tags, self.tags_str)


def run_async_test(coroutine):
    """运行异步测试函数的辅助方法"""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coroutine)


if __name__ == "__main__":
    unittest.main()
