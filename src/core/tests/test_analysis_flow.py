import pytest
import json
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from src.core.dialogue.analysis_flow import AnalysisFlow
from src.core.dialogue.models import ProcessingDialogue, DialogueContext, IntentAnalysis
from src.core.dialogue.pools import DialoguePool
from src.core.dialogue.enums import DialogueType, ProcessingStatus


@pytest.fixture
def mock_dialogue():
    """创建测试用对话"""
    return ProcessingDialogue(
        dialogue_index=1,
        opera_id=uuid4(),
        text="请帮我写一个Python脚本，用来处理CSV文件",
        type=DialogueType.NORMAL,
        status=ProcessingStatus.PENDING,
        context=DialogueContext(stage_index=1, related_dialogue_indices=[], conversation_state={}),
        created_at=datetime.now(timezone(timedelta(hours=8))),
        receiver_staff_ids=[uuid4()],
        is_narratage=False,
        is_whisper=False,
        tags="code_request",
        mentioned_staff_ids=[],
    )


@pytest.fixture
def mock_dialogue_pool(mock_dialogue):
    """创建测试用对话池"""
    pool = DialoguePool()
    # 添加一些相关的对话
    related_dialogue1 = ProcessingDialogue(
        dialogue_index=2,
        opera_id=mock_dialogue.opera_id,
        text="我们需要使用pandas库来处理数据",
        type=DialogueType.NORMAL,
        status=ProcessingStatus.COMPLETED,
        context=DialogueContext(stage_index=1, related_dialogue_indices=[], conversation_state={}),
        created_at=datetime.now(timezone(timedelta(hours=8))) - timedelta(minutes=5),
        receiver_staff_ids=[uuid4()],
        is_narratage=False,
        is_whisper=False,
        tags="",
        mentioned_staff_ids=[],
    )

    related_dialogue2 = ProcessingDialogue(
        dialogue_index=3,
        opera_id=mock_dialogue.opera_id,
        text="数据需要按照日期进行分组统计",
        type=DialogueType.NORMAL,
        status=ProcessingStatus.COMPLETED,
        context=DialogueContext(stage_index=1, related_dialogue_indices=[], conversation_state={}),
        created_at=datetime.now(timezone(timedelta(hours=8))) - timedelta(minutes=3),
        receiver_staff_ids=[uuid4()],
        is_narratage=False,
        is_whisper=False,
        tags="",
        mentioned_staff_ids=[],
    )

    pool.dialogues = [related_dialogue1, related_dialogue2, mock_dialogue]
    return pool


class TestAnalysisFlow:
    """测试AnalysisFlow类的功能"""

    @pytest.mark.asyncio
    async def test_check_intent_analysis(self, mock_dialogue, mock_dialogue_pool):
        """测试意图分析检查功能"""
        # 创建AnalysisFlow实例
        flow = AnalysisFlow(dialogue=mock_dialogue, temp_pool=mock_dialogue_pool)

        # 测试没有意图分析时
        assert flow.check_intent_analysis() == "analyze_intent"

        # 测试有意图分析时
        mock_dialogue.intent_analysis = IntentAnalysis(intent="code_generation", confidence=0.9, parameters={})
        assert flow.check_intent_analysis() == "analyze_context"

    @pytest.mark.asyncio
    async def test_analyze_intent(self, mock_dialogue, mock_dialogue_pool):
        """测试意图分析功能"""
        # 创建AnalysisFlow实例
        flow = AnalysisFlow(dialogue=mock_dialogue, temp_pool=mock_dialogue_pool)

        # 执行意图分析
        result = await flow.analyze_intent()

        # 验证结果
        assert result == "analyze_context"
        assert mock_dialogue.intent_analysis is not None
        assert mock_dialogue.intent_analysis.intent == "code_generation"
        assert mock_dialogue.intent_analysis.confidence > 0
        assert "code_request" in mock_dialogue.intent_analysis.parameters
        assert mock_dialogue.intent_analysis.parameters["is_code_request"] is True

    @pytest.mark.asyncio
    async def test_analyze_context(self, mock_dialogue, mock_dialogue_pool):
        """测试上下文分析功能"""
        # 创建AnalysisFlow实例
        flow = AnalysisFlow(dialogue=mock_dialogue, temp_pool=mock_dialogue_pool)

        # 先执行意图分析
        await flow.analyze_intent()

        # 执行上下文分析
        related_indices = await flow.analyze_context(mock_dialogue.intent_analysis)

        # 验证结果
        assert isinstance(related_indices, set)
        assert len(related_indices) > 0
        assert 2 in related_indices  # 验证是否关联到第一个相关对话
        assert 3 in related_indices  # 验证是否关联到第二个相关对话

        # 验证对话状态
        state = mock_dialogue.context.conversation_state
        assert "flow" in state
        assert "code_context" in state
        assert "decision_points" in state

        # 验证代码上下文
        code_context = state["code_context"]
        assert "pandas" in str(code_context).lower()
        assert "csv" in str(code_context).lower()

        # 验证主题信息
        flow = state["flow"]
        assert "topic_id" in flow
        assert "topic_type" in flow
        assert flow["topic_type"] == "code_generation"

    @pytest.mark.asyncio
    async def test_parse_intent_result(self, mock_dialogue, mock_dialogue_pool):
        """测试意图分析结果解析"""
        # 创建AnalysisFlow实例
        flow = AnalysisFlow(dialogue=mock_dialogue, temp_pool=mock_dialogue_pool)

        # 测试正常的代码生成请求
        result_str = json.dumps({
            "intent": "code_generation",
            "is_code_request": True,
            "code_details": {"type": "Python", "frameworks": ["pandas"], "requirements": ["CSV处理", "数据分析"]},
        })

        intent_analysis = flow._parse_intent_result(result_str)
        assert intent_analysis.intent == "code_generation"
        assert intent_analysis.confidence == 1.0
        assert intent_analysis.parameters["is_code_request"] is True
        assert "pandas" in str(intent_analysis.parameters["code_details"]["frameworks"])

        # 测试普通对话
        result_str = json.dumps({"intent": "general chat", "reason": "无实质性内容"})

        intent_analysis = flow._parse_intent_result(result_str)
        assert intent_analysis.intent == "general chat"
        assert intent_analysis.confidence == 0.1
        assert "reason" in intent_analysis.parameters

        # 测试解析失败的情况
        intent_analysis = flow._parse_intent_result("invalid json")
        assert intent_analysis.intent == ""
        assert intent_analysis.confidence == 0.1
        assert intent_analysis.parameters["reason"] == "解析失败"

    @pytest.mark.asyncio
    async def test_parse_context_result(self, mock_dialogue, mock_dialogue_pool):
        """测试上下文分析结果解析"""
        # 创建AnalysisFlow实例
        flow = AnalysisFlow(dialogue=mock_dialogue, temp_pool=mock_dialogue_pool)

        # 测试正常的上下文分析结果
        result_str = json.dumps({
            "conversation_flow": {"topic_id": "test-topic-123", "topic_type": "code_generation", "current_topic": "CSV数据处理"},
            "code_context": {
                "requirements": ["数据处理", "使用pandas"],
                "frameworks": ["pandas"],
                "file_structure": ["src/process_csv.py"],
            },
            "decision_points": [
                {"dialogue_index": 2, "topic_id": "test-topic-123", "decision": "使用pandas库"},
                {"dialogue_index": 3, "topic_id": "test-topic-123", "decision": "按日期分组"},
            ],
        })

        related_indices = flow._parse_context_result(result_str)
        assert isinstance(related_indices, set)
        assert len(related_indices) == 2
        assert 2 in related_indices
        assert 3 in related_indices

        # 验证对话状态更新
        state = mock_dialogue.context.conversation_state
        assert "flow" in state
        assert state["flow"]["topic_type"] == "code_generation"
        assert "code_context" in state
        assert "decision_points" in state
        assert len(state["decision_points"]) == 2

        # 测试缺少必要字段的情况
        result_str = json.dumps({"conversation_flow": {"topic_id": "test-topic-123"}})

        related_indices = flow._parse_context_result(result_str)
        assert isinstance(related_indices, set)
        assert len(related_indices) == 0

        # 测试解析失败的情况
        related_indices = flow._parse_context_result("invalid json")
        assert isinstance(related_indices, set)
        assert len(related_indices) == 0

    @pytest.mark.asyncio
    async def test_handle_code_request(self, mock_dialogue, mock_dialogue_pool):
        """测试代码生成请求处理"""
        # 创建AnalysisFlow实例
        flow = AnalysisFlow(dialogue=mock_dialogue, temp_pool=mock_dialogue_pool)

        # 测试处理代码生成请求
        analysis_result = {
            "is_code_request": True,
            "code_details": {
                "type": "python",
                "frameworks": ["pandas", "numpy"],
                "resources": [
                    {"type": "python", "file_path": "src/process_data.py"},
                    {"type": "csv", "file_path": "data/input.csv"},
                ],
            },
        }

        flow._handle_code_request(analysis_result)

        # 验证标签更新
        assert "code_request" in mock_dialogue.tags
        assert "code_type_python" in mock_dialogue.tags
        assert "code_type_csv" in mock_dialogue.tags
        assert "framework_pandas" in mock_dialogue.tags
        assert "framework_numpy" in mock_dialogue.tags
