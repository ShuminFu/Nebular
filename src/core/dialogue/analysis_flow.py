from crewai.flow.flow import Flow, listen, start, router, or_
from typing import Dict, Set
from pydantic import BaseModel

from src.core.dialogue.models import ProcessingDialogue, IntentAnalysis
from src.core.dialogue.pools import DialoguePool
from src.core.dialogue.enums import EXT_TO_MIME_TYPE
from src.crewai_ext.crew_bases.analyzers_crewbase import (
    IntentAnalyzerCrew,
    ContextAnalyzerCrew,
    IntentAnalysisInputs,
    ContextAnalysisInputs,
)


# 在AnalysisFlow类之前添加状态模型
class AnalysisState(BaseModel):
    intent_flag: bool = False
    intent_analysis: IntentAnalysis = None
    related_indices: Set[int] = set()


# 修改类继承
class AnalysisFlow(Flow[AnalysisState]):
    """对话分析流程

    将意图分析和上下文分析整合到一个Flow中。
    确保意图分析的结果能正确传递给上下文分析，
    并维护临时对话池的状态。
    """

    def __init__(self, dialogue: ProcessingDialogue, temp_pool: DialoguePool):
        """初始化分析流程

        Args:
            dialogue: 要分析的对话
            temp_pool: 临时对话池，用于上下文分析
        """
        super().__init__()  # 新增父类初始化调用

        self.dialogue = dialogue
        self.temp_pool = temp_pool
        # 初始化分析器
        self.intent_crew = IntentAnalyzerCrew()
        self.context_crew = ContextAnalyzerCrew()

    @start()
    def start_method(self):
        """初始化状态并设置意图分析标志"""
        # 使用类型安全的属性访问
        self.state.intent_flag = bool(self.dialogue.intent_analysis)

    @listen("route_analyze_intent")
    async def analyze_intent(self):
        """分析对话意图

        Returns:
            IntentAnalysis: 意图分析结果
        """
        # 准备意图分析输入
        intent_inputs = IntentAnalysisInputs(
            text=self.dialogue.text,
            type=self.dialogue.type.name,
            is_narratage=self.dialogue.is_narratage,
            is_whisper=self.dialogue.is_whisper,
            tags=self.dialogue.tags,
            mentioned_staff_bools=bool(self.dialogue.mentioned_staff_ids),
            opera_id=str(self.dialogue.opera_id) if self.dialogue.opera_id else None,
            dialogue_index=self.dialogue.dialogue_index,
            stage_index=self.dialogue.context.stage_index if self.dialogue.context else None,
        )

        # 执行意图分析
        result = await self.intent_crew.crew().kickoff_async(inputs=intent_inputs.model_dump())

        # 解析结果并更新对话的意图分析
        intent_analysis = self._parse_intent_result(result.raw)
        self.dialogue.intent_analysis = intent_analysis

        # 将分析结果存储在Flow状态中
        self.state.intent_analysis = intent_analysis

        self.state.intent_flag = True

    @router(or_(start_method, analyze_intent))
    def check_intent_analysis(self):
        """检查是否需要意图分析"""
        if not self.state.intent_flag:
            return "route_analyze_intent"
        # 直接跳转到语境分析
        return "route_analyze_context"

    @listen("route_analyze_context")
    async def analyze_context(self) -> Set[int]:
        """分析对话上下文

        Args:
            intent_analysis: 意图分析结果

        Returns:
            Set[int]: 相关对话的索引集合
        """
        intent_analysis = self.state.intent_analysis
        # 获取当前stage的对话
        current_stage = self.dialogue.context.stage_index if self.dialogue.context else None
        stage_dialogues = []

        if current_stage is not None:
            # 获取当前stage的对话（排除当前对话）
            stage_dialogues.extend([
                d
                for d in self.temp_pool.dialogues
                if d.context and d.context.stage_index == current_stage and d.dialogue_index != self.dialogue.dialogue_index
            ])

            # 如果当前stage > 1，则获取前一个stage的对话
            if current_stage > 1:
                stage_dialogues.extend([
                    d for d in self.temp_pool.dialogues if d.context and d.context.stage_index == current_stage - 1
                ])

        # 准备上下文分析输入
        context_inputs = ContextAnalysisInputs(
            opera_id=str(self.dialogue.opera_id),
            dialogue_index=self.dialogue.dialogue_index,
            text=self.dialogue.text,
            type=self.dialogue.type.name,
            tags=self.dialogue.tags,
            stage_index=self.dialogue.context.stage_index if self.dialogue.context else None,
            intent_analysis=intent_analysis.intent,
            dialogue_same_stage=[
                {"index": d.dialogue_index, "text": d.text, "type": d.type.name, "tags": d.tags} for d in stage_dialogues[-10:]
            ],  # 只取最近10条对话
        )

        # 执行上下文分析
        result = await self.context_crew.crew().kickoff_async(inputs=context_inputs.model_dump())

        # 解析结果并更新对话的上下文
        related_indices = self._parse_context_result(result.raw)

        # 将分析结果存储在Flow状态中
        self.state.related_indices = related_indices

        return related_indices

    def _parse_intent_result(self, result_str: str) -> IntentAnalysis:
        """解析意图分析结果

        Args:
            result_str: 原始结果字符串

        Returns:
            IntentAnalysis: 解析后的意图分析结果
        """
        import json

        try:
            # 移除可能的Markdown代码块标记
            if result_str.startswith("```json\n"):
                result_str = result_str[8:]
            if result_str.endswith("\n```"):
                result_str = result_str[:-4]

            analysis_result = json.loads(result_str)
            intent = analysis_result.get("intent", "").strip()

            # 如果意图为空（无意义对话），返回基本分析结果
            if intent == "general chat":
                return IntentAnalysis(
                    intent="general chat",
                    confidence=0.1,
                    parameters={
                        "text": self.dialogue.text,
                        "type": self.dialogue.type.name,
                        "tags": self.dialogue.tags,
                        "reason": analysis_result.get("reason", "无实质性内容"),
                    },
                )

            # 处理代码生成请求
            if analysis_result.get("is_code_request"):
                self._handle_code_request(analysis_result)

            return IntentAnalysis(
                intent=intent,
                confidence=1.0 if analysis_result.get("is_code_request") else 0.8,
                parameters={
                    "text": self.dialogue.text,
                    "type": self.dialogue.type.name,
                    "tags": self.dialogue.tags,
                    "is_code_request": analysis_result.get("is_code_request", False),
                    "code_details": analysis_result.get("code_details", {}),
                },
            )

        except json.JSONDecodeError:
            # 如果解析失败，返回基本的意图分析
            return IntentAnalysis(
                intent="",
                confidence=0.1,
                parameters={
                    "text": self.dialogue.text,
                    "type": self.dialogue.type.name,
                    "tags": self.dialogue.tags,
                    "reason": "解析失败",
                },
            )

    def _parse_context_result(self, result_str: str) -> Set[int]:
        """解析上下文分析结果

        Args:
            result_str: 原始结果字符串

        Returns:
            Set[int]: 相关对话的索引集合
        """
        import json
        from datetime import datetime, timezone, timedelta

        try:
            # 使用ApiResponseParser解析结果
            context_data = json.loads(result_str)

            # 验证必要的字段
            required_fields = ["conversation_flow", "code_context", "decision_points"]
            if not all(field in context_data for field in required_fields):
                raise ValueError("上下文数据结构缺少必要字段")

            # 验证主题相关字段
            flow = context_data["conversation_flow"]
            if not all(field in flow for field in ["topic_id", "topic_type", "current_topic"]):
                raise ValueError("conversation_flow缺少主题相关字段")

            # 更新conversation_state
            now = datetime.now(timezone(timedelta(hours=8)))
            self.dialogue.context.conversation_state.update({
                "flow": flow,
                "code_context": context_data["code_context"],
                "decision_points": context_data["decision_points"],
                "topic": {
                    "id": flow["topic_id"],
                    "type": flow["topic_type"],
                    "name": flow["current_topic"],
                },
                "analyzed_at": now.isoformat(),
            })

            # 从decision_points中提取相关的对话索引
            related_indices = {
                int(point["dialogue_index"])
                for point in context_data["decision_points"]
                if "dialogue_index" in point
                and str(point["dialogue_index"]).isdigit()
                and point.get("topic_id") == flow["topic_id"]  # 确保只关联同一主题的对话
            }

            # 更新对话的相关索引
            self.dialogue.context.related_dialogue_indices = list(related_indices)

            return related_indices

        except (ValueError, KeyError, AttributeError, json.JSONDecodeError) as e:
            print(f"解析上下文数据结构失败: {str(e)}")
            return set()

    def _handle_code_request(self, analysis_result: Dict) -> None:
        """处理代码生成请求的特殊逻辑

        Args:
            analysis_result: 意图分析结果字典
        """
        code_details = analysis_result.get("code_details", {})

        # 获取所有文件的类型，用于标签
        file_types = set()
        frameworks = set()

        # 处理每个资源文件的信息
        for resource in code_details.get("resources", []):
            file_type = resource.get("type", "").lower()
            file_types.add(f"code_type_{file_type}")

            # 添加MIME类型映射
            if "mime_type" not in resource:
                ext = resource["file_path"].lower().split(".")[-1]
                resource["mime_type"] = EXT_TO_MIME_TYPE.get(ext, "text/plain")

        # 收集所有框架
        frameworks.update(code_details.get("frameworks", []))

        # 构建标签列表
        code_tags = [
            "code_request",  # 标记这是一个代码生成请求
            *file_types,  # 添加所有文件类型标签
            *[f"framework_{f.lower()}" for f in frameworks],  # 添加框架标签
        ]

        # 更新对话标签
        if self.dialogue.tags:
            self.dialogue.tags = f"{self.dialogue.tags},{','.join(code_tags)}"
        else:
            self.dialogue.tags = ",".join(code_tags)
