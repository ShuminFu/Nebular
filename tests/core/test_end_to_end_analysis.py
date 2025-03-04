import unittest
import asyncio
import json
from uuid import uuid4

from src.core.dialogue.models import ProcessingDialogue, IntentAnalysis
from src.core.dialogue.pools import DialoguePool
from src.core.dialogue.enums import DialogueType, ProcessingStatus
from src.opera_service.signalr_client.opera_signalr_client import MessageReceivedArgs
from src.crewai_ext.flows.analysis_flow import AnalysisFlow
from src.crewai_ext.crew_bases.analyzers_crewbase import IntentAnalyzerCrew
from src.core.logger_config import get_logger


class TestEndToEndAnalysis(unittest.TestCase):
    """端到端测试分析流程，使用真实组件

    这个测试类从真实消息开始，触发整个处理链，包括:
    1. 创建ProcessingDialogue
    2. 通过AnalysisFlow提取ResourcesForViewing标签内容
    3. 意图分析
    4. 上下文分析
    """

    def setUp(self):
        """设置测试环境"""
        # 配置日志
        self.logger = get_logger("TestEndToEnd", "logs/test_end_to_end.log")

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

        # 创建MessageReceivedArgs实例 (不使用模拟对象以便于调试)
        self.message_args = self._create_message_received_args()

        # 创建对话池
        self.dialogue_pool = DialoguePool()

        # 创建意图分析器
        self.intent_analyzer = IntentAnalyzerCrew()

    def _create_message_received_args(self):
        """创建MessageReceivedArgs实例"""

        class TestMessageArgs:
            """用于测试的简单消息参数类"""

            def __init__(self):
                self.index = 1
                self.opera_id = uuid4()
                self.sender_staff_id = uuid4()
                self.text = "请查看这些资源，并告诉我main.js文件中的主要功能"
                self.tags = None
                self.mentioned_staff_ids = [uuid4()]
                self.receiver_staff_ids = [uuid4()]
                self.is_narratage = False
                self.is_whisper = False

        # 创建并返回参数实例
        args = TestMessageArgs()
        args.tags = self.tags_str
        return args

    def test_extract_resources_viewing_format(self):
        """测试ResourcesForViewing格式的资源提取"""
        # 从消息创建对话对象
        dialogue = ProcessingDialogue(
            dialogue_index=self.message_args.index,
            opera_id=self.message_args.opera_id,
            sender_staff_id=self.message_args.sender_staff_id,
            receiver_staff_ids=self.message_args.receiver_staff_ids,
            text_content=self.message_args.text,
            tags=self.message_args.tags,
            mentioned_staff_ids=self.message_args.mentioned_staff_ids,
            type=DialogueType.NORMAL,
        )

        # 创建AnalysisFlow
        flow = AnalysisFlow(dialogue, self.dialogue_pool)

        # 提取资源
        resources = flow._extract_resources_from_tags(dialogue.tags)

        # 验证结果
        self.assertEqual(len(resources), 2)
        self.assertEqual(resources[0]["file_path"], "/src/js/main.js")
        self.assertEqual(resources[0]["resource_id"], "1679d89d-40d3-4db2-b7f5-a48881d3aa31")
        self.assertEqual(resources[1]["file_path"], "/src/css/style.css")
        self.assertEqual(resources[1]["resource_id"], "368e4fd9-e40b-4b18-a48b-1003e71c4aac")

    def test_run_async_end_to_end(self):
        """运行异步端到端测试的同步包装器"""
        # 这个方法只是运行asyncio.run并调用真正的测试方法
        asyncio.run(self.run_end_to_end())

    async def run_end_to_end(self):
        """端到端运行分析流程

        1. 从消息创建对话
        2. 将对话添加到对话池
        3. 创建分析流程
        4. 启动分析流程
        5. 验证分析结果
        """
        # 从消息创建对话对象
        dialogue = ProcessingDialogue(
            dialogue_index=self.message_args.index,
            opera_id=self.message_args.opera_id,
            sender_staff_id=self.message_args.sender_staff_id,
            receiver_staff_ids=getattr(self.message_args, "receiver_staff_ids", []),
            text_content=self.message_args.text,
            tags=self.message_args.tags,
            mentioned_staff_ids=self.message_args.mentioned_staff_ids,
            type=DialogueType.NORMAL,
        )

        # 将对话添加到对话池
        await self.dialogue_pool.add_dialogue(dialogue)

        # 手动设置意图分析结果 (在真实情况下这会由意图分析器完成)
        dialogue.intent_analysis = IntentAnalysis(
            intent="view_resources", confidence=0.95, parameters={"resource_type": "js", "action": "explain"}
        )
        dialogue.status = ProcessingStatus.PROCESSING

        # 创建分析流程
        flow = AnalysisFlow(dialogue, self.dialogue_pool)

        # 断点建议: 在下一行设置断点来调试整个流程
        # 启动分析流程
        flow.start_method()

        # 验证资源已被提取
        resources = flow._extract_resources_from_tags(dialogue.tags)
        self.assertEqual(len(resources), 2)

        # 这里之后的测试将取决于真实的AnalysisFlow行为
        # 在实际调试中，你可以观察整个流程并验证中间步骤

    def test_end_to_end_full_trace(self):
        """用于调试的详细跟踪测试

        这个测试方法在调试时特别有用，可以在关键点设置断点并步进执行
        """
        # 步骤 1: 创建对话对象
        dialogue = ProcessingDialogue(
            dialogue_index=self.message_args.index,
            opera_id=self.message_args.opera_id,
            sender_staff_id=self.message_args.sender_staff_id,
            receiver_staff_ids=getattr(self.message_args, "receiver_staff_ids", []),
            text_content=self.message_args.text,
            tags=self.message_args.tags,
            mentioned_staff_ids=self.message_args.mentioned_staff_ids,
            type=DialogueType.NORMAL,
        )

        self.logger.debug("步骤 1 完成: 创建对话对象")
        self.logger.debug(f"对话内容: {dialogue.text}")
        self.logger.debug(f"对话标签: {dialogue.tags}")

        # 步骤 2: 将对话添加到对话池
        # 非异步测试中使用同步调用
        asyncio.run(self.dialogue_pool.add_dialogue(dialogue))
        self.logger.debug("步骤 2 完成: 将对话添加到对话池")

        # 步骤 3: 执行意图分析 (模拟)
        dialogue.intent_analysis = IntentAnalysis(
            intent="view_resources", confidence=0.95, parameters={"resource_type": "js", "action": "explain"}
        )
        dialogue.status = ProcessingStatus.PROCESSING
        self.logger.debug("步骤 3 完成: 执行意图分析")
        self.logger.debug(f"意图: {dialogue.intent_analysis.intent}")
        self.logger.debug(f"参数: {dialogue.intent_analysis.parameters}")

        # 步骤 4: 创建分析流程
        flow = AnalysisFlow(dialogue, self.dialogue_pool)
        self.logger.debug("步骤 4 完成: 创建分析流程")

        # 步骤 5: 提取资源
        resources = flow._extract_resources_from_tags(dialogue.tags)
        self.logger.debug("步骤 5 完成: 提取资源")
        self.logger.debug(f"提取到的资源: {resources}")

        # 验证资源提取结果
        self.assertEqual(len(resources), 2)
        self.assertEqual(resources[0]["file_path"], "/src/js/main.js")
        self.assertEqual(resources[0]["resource_id"], "1679d89d-40d3-4db2-b7f5-a48881d3aa31")

        # 这里可以设置断点进行调试
        # 调试完成后，将状态设置为已处理
        dialogue.status = ProcessingStatus.COMPLETED


if __name__ == "__main__":
    unittest.main()
