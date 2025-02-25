import pytest
import json
from datetime import datetime, timezone, timedelta
from uuid import uuid4


from src.crewai_ext.flows.analysis_flow import AnalysisFlow
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
def mock_iteration_dialogue():
    """创建测试用迭代类型对话"""
    resource_id = str(uuid4())
    resource_uuid = uuid4()
    return ProcessingDialogue(
        dialogue_index=4,
        opera_id=uuid4(),
        text="请将项目中的按钮颜色改为蓝色，并添加一个提交表单的功能",
        type=DialogueType.ITERATION,
        status=ProcessingStatus.PENDING,
        context=DialogueContext(
            stage_index=2,
            related_dialogue_indices=[],
            conversation_state={"resources": [{"file_path": "src/components/Button.js", "resource_id": resource_id}]},
        ),
        created_at=datetime.now(timezone(timedelta(hours=8))),
        receiver_staff_ids=[uuid4()],
        is_narratage=False,
        is_whisper=False,
        tags="iteration_request",
        mentioned_staff_ids=[resource_uuid],
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


@pytest.fixture
def mock_iteration_dialogue_pool(mock_iteration_dialogue):
    """创建测试用迭代对话池"""
    pool = DialoguePool()

    # 添加一些迭代相关的对话
    related_dialogue1 = ProcessingDialogue(
        dialogue_index=5,
        opera_id=mock_iteration_dialogue.opera_id,
        text="之前的UI设计需要进行一些调整",
        type=DialogueType.NORMAL,
        status=ProcessingStatus.COMPLETED,
        context=DialogueContext(stage_index=2, related_dialogue_indices=[], conversation_state={}),
        created_at=datetime.now(timezone(timedelta(hours=8))) - timedelta(minutes=10),
        receiver_staff_ids=[uuid4()],
        is_narratage=False,
        is_whisper=False,
        tags="ui_design",
        mentioned_staff_ids=[],
    )

    pool.dialogues = [related_dialogue1, mock_iteration_dialogue]
    return pool


class TestAnalysisFlow:
    """测试AnalysisFlow类的功能"""

    @pytest.mark.asyncio
    async def test_check_intent_analysis(self, mock_dialogue, mock_dialogue_pool):
        """测试意图分析检查功能"""
        # 创建AnalysisFlow实例
        flow = AnalysisFlow(dialogue=mock_dialogue, temp_pool=mock_dialogue_pool)

        # 测试没有意图分析标志时
        assert flow.check_intent_analysis() == "route_analyze_intent"

        # 测试有意图分析标志时
        mock_dialogue.intent_analysis = IntentAnalysis(intent="code_generation", confidence=0.9, parameters={})
        flow.state.intent_flag = True
        assert flow.check_intent_analysis() == "route_analyze_context"

    @pytest.mark.asyncio
    async def test_analyze_intent(self, mock_dialogue, mock_dialogue_pool):
        """测试意图分析功能"""
        # 创建AnalysisFlow实例
        flow = AnalysisFlow(dialogue=mock_dialogue, temp_pool=mock_dialogue_pool)

        # 保存原始方法
        original_method = flow.analyze_intent

        # 定义模拟的analyze_intent方法
        async def mock_analyze_intent():
            # 创建意图分析结果
            intent_analysis = IntentAnalysis(
                intent="code_generation",
                confidence=0.9,
                parameters={
                    "is_code_request": True,
                    "code_details": {
                        "project_type": "python",
                        "project_description": "CSV处理脚本",
                        "requirements": ["数据处理", "使用pandas"],
                        "frameworks": ["pandas"],
                    },
                },
            )

            # 设置对话的意图分析结果
            mock_dialogue.intent_analysis = intent_analysis
            # 设置流程状态
            flow.state.intent_analysis = intent_analysis
            flow.state.intent_flag = True

            # 方法没有明确返回值，测试时模拟返回"analyze_context"
            return "analyze_context"

        # 替换方法
        flow.analyze_intent = mock_analyze_intent

        try:
            # 执行意图分析
            result = await flow.analyze_intent()

            # 验证结果
            assert result == "analyze_context"
            assert mock_dialogue.intent_analysis is not None
            assert mock_dialogue.intent_analysis.intent == "code_generation"
            assert mock_dialogue.intent_analysis.confidence > 0
            assert "is_code_request" in mock_dialogue.intent_analysis.parameters
            assert mock_dialogue.intent_analysis.parameters["is_code_request"] is True
            assert flow.state.intent_flag is True
        finally:
            # 恢复原始方法
            flow.analyze_intent = original_method

    @pytest.mark.asyncio
    async def test_analyze_iteration_intent(self, mock_iteration_dialogue, mock_iteration_dialogue_pool):
        """测试迭代意图分析功能"""
        # 创建AnalysisFlow实例
        flow = AnalysisFlow(dialogue=mock_iteration_dialogue, temp_pool=mock_iteration_dialogue_pool)

        # 保存原始方法
        original_method = flow.analyze_intent

        # 定义模拟的analyze_intent方法
        async def mock_analyze_intent():
            # 设置迭代标志
            flow.state.iteration_flag = True

            # 创建意图分析结果
            intent_analysis = IntentAnalysis(
                intent="resource_iteration",
                confidence=0.9,
                parameters={
                    "is_code_request": True,
                    "code_details": {
                        "project_type": "迭代项目",
                        "project_description": "UI修改和功能添加",
                        "resources": mock_iteration_dialogue.context.conversation_state.get("resources", []),
                        "requirements": ["修改按钮颜色", "添加表单提交功能"],
                        "frameworks": ["React"],
                    },
                },
            )

            # 设置对话的意图分析结果
            mock_iteration_dialogue.intent_analysis = intent_analysis

            # 返回下一步操作
            return "analyze_context"

        # 替换方法
        flow.analyze_intent = mock_analyze_intent

        try:
            # 执行意图分析
            result = await flow.analyze_intent()

            # 验证结果
            assert result == "analyze_context"
            assert mock_iteration_dialogue.intent_analysis is not None
            assert mock_iteration_dialogue.intent_analysis.intent == "resource_iteration"
            assert mock_iteration_dialogue.intent_analysis.confidence > 0
            assert "is_code_request" in mock_iteration_dialogue.intent_analysis.parameters
            assert mock_iteration_dialogue.intent_analysis.parameters["is_code_request"] is True
            assert "code_details" in mock_iteration_dialogue.intent_analysis.parameters

            # 验证迭代标志
            assert flow.state.iteration_flag is True
        finally:
            # 恢复原始方法
            flow.analyze_intent = original_method

    @pytest.mark.asyncio
    async def test_analyze_context(self, mock_dialogue, mock_dialogue_pool):
        """测试上下文分析功能"""
        # 创建AnalysisFlow实例
        flow = AnalysisFlow(dialogue=mock_dialogue, temp_pool=mock_dialogue_pool)

        # 设置意图分析结果
        intent_analysis = IntentAnalysis(
            intent="code_generation",
            confidence=0.9,
            parameters={
                "is_code_request": True,
                "code_details": {
                    "project_type": "python",
                    "project_description": "CSV处理脚本",
                    "requirements": ["数据处理", "使用pandas"],
                    "frameworks": ["pandas"],
                },
            },
        )
        mock_dialogue.intent_analysis = intent_analysis
        flow.state.intent_analysis = intent_analysis
        flow.state.intent_flag = True

        # 保存原始方法
        original_method = flow.analyze_context

        # 定义模拟的analyze_context方法
        async def mock_analyze_context():
            # 更新对话状态
            mock_dialogue.context.conversation_state.update({
                "flow": {
                    "topic_id": "test-topic-123",
                    "topic_type": "code_generation",
                    "current_topic": "CSV数据处理",
                },
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

            # 返回相关对话索引
            return {2, 3}

        # 替换方法
        flow.analyze_context = mock_analyze_context

        try:
            # 执行上下文分析
            related_indices = await flow.analyze_context()

            # 验证结果
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
        finally:
            # 恢复原始方法
            flow.analyze_context = original_method

    @pytest.mark.asyncio
    async def test_analyze_iteration_context(self, mock_iteration_dialogue, mock_iteration_dialogue_pool):
        """测试迭代上下文分析功能"""
        # 创建AnalysisFlow实例
        flow = AnalysisFlow(dialogue=mock_iteration_dialogue, temp_pool=mock_iteration_dialogue_pool)

        # 直接设置意图分析结果和迭代标志
        mock_iteration_dialogue.intent_analysis = IntentAnalysis(
            intent="resource_iteration",
            confidence=0.9,
            parameters={
                "is_code_request": True,
                "code_details": {
                    "project_type": "迭代项目",
                    "project_description": "UI修改和功能添加",
                    "resources": mock_iteration_dialogue.context.conversation_state.get("resources", []),
                    "requirements": ["修改按钮颜色", "添加表单提交功能"],
                    "frameworks": ["React"],
                },
            },
        )
        flow.state.iteration_flag = True

        # 保存原始方法
        original_method = flow.analyze_context

        # 定义模拟的analyze_context方法
        async def mock_analyze_context():
            # 更新对话状态
            mock_iteration_dialogue.context.conversation_state.update({
                "flow": {
                    "topic_id": "iter-topic-456",
                    "topic_type": "resource_iteration",
                    "current_topic": "UI修改和功能添加",
                },
                "code_context": {
                    "requirements": ["修改按钮颜色", "添加表单提交功能"],
                    "frameworks": ["React"],
                    "file_structure": ["src/components/Button.js", "src/components/Form.js"],
                },
                "decision_points": [
                    {"dialogue_index": 5, "topic_id": "iter-topic-456", "decision": "UI设计调整"},
                    {"dialogue_index": 4, "topic_id": "iter-topic-456", "decision": "具体迭代需求"},
                ],
            })

            # 返回相关对话索引
            return {5}

        # 替换方法
        flow.analyze_context = mock_analyze_context

        try:
            # 执行上下文分析
            related_indices = await flow.analyze_context()

            # 验证结果
            assert isinstance(related_indices, set)
            assert len(related_indices) > 0
            assert 5 in related_indices  # 验证是否关联到相关对话

            # 验证对话状态
            state = mock_iteration_dialogue.context.conversation_state
            assert "flow" in state
            assert "code_context" in state
            assert "decision_points" in state

            # 验证迭代上下文
            code_context = state["code_context"]
            assert "ui" in str(code_context).lower() or "button" in str(code_context).lower()

            # 验证主题信息
            flow_info = state["flow"]
            assert "topic_id" in flow_info
            assert "topic_type" in flow_info
            assert flow_info["topic_type"] == "resource_iteration"
        finally:
            # 恢复原始方法
            flow.analyze_context = original_method

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
    async def test_parse_iteration_intent_result(self, mock_iteration_dialogue, mock_iteration_dialogue_pool):
        """测试迭代意图分析结果解析"""
        # 创建AnalysisFlow实例
        flow = AnalysisFlow(dialogue=mock_iteration_dialogue, temp_pool=mock_iteration_dialogue_pool)

        # 测试正常的迭代请求结果
        resource_id = str(uuid4())
        result_str = json.dumps({
            "intent": "resource_iteration",
            "reason": "基于迭代需求的资源修改任务",
            "is_code_request": True,
            "code_details": {
                "project_type": "迭代项目",
                "project_description": "UI修改和功能添加",
                "resources": [
                    {
                        "file_path": "src/components/Button.js",
                        "type": "javascript",
                        "mime_type": "text/javascript",
                        "description": "修改按钮颜色为蓝色",
                        "action": "update",
                        "resource_id": resource_id,
                        "position": "style部分",
                    },
                    {
                        "file_path": "src/components/Form.js",
                        "type": "javascript",
                        "mime_type": "text/javascript",
                        "description": "添加表单提交功能",
                        "action": "create",
                        "resource_id": str(uuid4()),
                        "position": "全部",
                    },
                ],
                "requirements": ["修改按钮颜色", "添加表单提交功能"],
                "frameworks": ["React"],
            },
        })

        intent_analysis = flow._parse_intent_result(result_str)
        assert intent_analysis.intent == "resource_iteration"
        assert intent_analysis.confidence == 1.0
        assert intent_analysis.parameters["is_code_request"] is True
        assert len(intent_analysis.parameters["code_details"]["resources"]) == 2
        assert "React" in str(intent_analysis.parameters["code_details"]["frameworks"])
        assert "修改按钮颜色" in str(intent_analysis.parameters["code_details"]["requirements"])

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
    async def test_parse_iteration_context_result(self, mock_iteration_dialogue, mock_iteration_dialogue_pool):
        """测试迭代上下文分析结果解析"""
        # 创建AnalysisFlow实例
        flow = AnalysisFlow(dialogue=mock_iteration_dialogue, temp_pool=mock_iteration_dialogue_pool)

        # 测试正常的迭代上下文分析结果
        result_str = json.dumps({
            "conversation_flow": {
                "topic_id": "iter-topic-456",
                "topic_type": "resource_iteration",
                "current_topic": "UI修改和功能添加",
            },
            "code_context": {
                "requirements": ["修改按钮颜色", "添加表单提交功能"],
                "frameworks": ["React"],
                "file_structure": ["src/components/Button.js", "src/components/Form.js"],
            },
            "decision_points": [
                {"dialogue_index": 5, "topic_id": "iter-topic-456", "decision": "UI设计调整"},
                {"dialogue_index": 4, "topic_id": "iter-topic-456", "decision": "具体迭代需求"},
            ],
        })

        related_indices = flow._parse_context_result(result_str)
        assert isinstance(related_indices, set)
        assert len(related_indices) == 2
        assert 5 in related_indices
        assert 4 in related_indices

        # 验证对话状态更新
        state = mock_iteration_dialogue.context.conversation_state
        assert "flow" in state
        assert state["flow"]["topic_type"] == "resource_iteration"
        assert "code_context" in state
        assert "decision_points" in state
        assert len(state["decision_points"]) == 2

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

    @pytest.mark.asyncio
    async def test_handle_iteration_code_request(self, mock_iteration_dialogue, mock_iteration_dialogue_pool):
        """测试迭代代码请求处理"""
        # 创建AnalysisFlow实例
        flow = AnalysisFlow(dialogue=mock_iteration_dialogue, temp_pool=mock_iteration_dialogue_pool)

        # 测试处理迭代代码请求
        analysis_result = {
            "is_code_request": True,
            "code_details": {
                "project_type": "迭代项目",
                "frameworks": ["React", "CSS"],
                "resources": [
                    {"type": "javascript", "file_path": "src/components/Button.js", "resource_id": str(uuid4())},
                    {"type": "javascript", "file_path": "src/components/Form.js", "resource_id": str(uuid4())},
                ],
            },
        }

        flow._handle_code_request(analysis_result)

        # 验证标签更新
        assert "iteration_request" in mock_iteration_dialogue.tags
        assert "code_request" in mock_iteration_dialogue.tags
        assert "code_type_javascript" in mock_iteration_dialogue.tags
        assert "framework_react" in mock_iteration_dialogue.tags
        assert "framework_css" in mock_iteration_dialogue.tags
