import json
from typing import Set

from src.core.dialogue.enums import DialogueType, EXT_TO_MIME_TYPE
from src.core.dialogue.models import ProcessingDialogue, IntentAnalysis
from src.core.dialogue.pools import DialoguePool
from src.core.parser.api_response_parser import ApiResponseParser
from src.core.logger_config import get_logger
from src.crewai_ext.crew_bases.analyzers_crewbase import (
    IntentAnalysisInputs,
    ContextAnalysisInputs,
    IntentAnalyzerCrew,
    ContextAnalyzerCrew,
)

# 初始化logger
logger = get_logger("dialogue_analyzer", "logs/llm_analyzer.log")


class DialogueAnalyzer:
    """对话分析器

    使用CrewAI实现的对话分析器，负责：
    1. 意图识别
    2. 上下文关联分析
    3. Opera隔离
    4. 代码生成请求识别
    """

    def analyze_intent(self, dialogue: ProcessingDialogue) -> IntentAnalysis:
        """分析单个对话的意图

        能判断对代码生成请求的识别：
        1. 识别是否是代码生成请求
        2. 提取代码类型和要求
        3. 分析代码生成的上下文
        4. 识别并过滤无意义对话
        5. 支持多文件代码生成场景

        Args:
            dialogue: 要分析的对话

        Returns:
            IntentAnalysis: 意图分析结果，对于无意义对话，intent为空字符串，confidence为0.1
        """
        intent_inputs = IntentAnalysisInputs(
            text=dialogue.text,
            type=dialogue.type.name,
            is_narratage=dialogue.is_narratage,
            is_whisper=dialogue.is_whisper,
            tags=dialogue.tags,
            mentioned_staff_bools=bool(dialogue.mentioned_staff_ids),
        )

        logger.info(
            f"[LLM Input] Intent Analysis Task for dialogue {dialogue.dialogue_index}:\n{intent_inputs.model_dump_json()}"
        )

        # 执行分析
        intent_crew = IntentAnalyzerCrew()
        result = intent_crew.crew().kickoff(inputs=intent_inputs)

        # 记录LLM输出
        logger.info(f"[LLM Output] Intent Analysis Result for dialogue {dialogue.dialogue_index}:\n{result.raw}")

        try:
            # 解析结果
            result_str = result.raw
            # 移除可能的Markdown代码块标记
            if result_str.startswith("```json\n"):
                result_str = result_str[8:]
            if result_str.endswith("\n```"):
                result_str = result_str[:-4]

            analysis_result = json.loads(result_str)
            intent = analysis_result.get("intent", "").strip()

            # 如果意图为空（无意义对话），返回基本分析结果
            if not intent:
                return IntentAnalysis(
                    intent="",
                    confidence=0.1,
                    parameters={
                        "text": dialogue.text,
                        "type": dialogue.type.name,
                        "tags": dialogue.tags,
                        "reason": analysis_result.get("reason", "无实质性内容"),
                    },
                )

            # 如果是代码生成请求，处理多文件信息
            if analysis_result.get("is_code_request"):
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
                        resource["mime_type"] = self._get_mime_type(resource["file_path"])

                # 收集所有框架
                frameworks.update(code_details.get("frameworks", []))

                # 构建标签列表
                code_tags = [
                    "code_request",  # 标记这是一个代码生成请求
                    *file_types,  # 添加所有文件类型标签
                    *[f"framework_{f.lower()}" for f in frameworks],  # 添加框架标签
                ]

                # 更新对话标签
                if dialogue.tags:
                    dialogue.tags = f"{dialogue.tags},{','.join(code_tags)}"
                else:
                    dialogue.tags = ",".join(code_tags)

                # 更新对话类型
                dialogue.type = DialogueType.CODE_RESOURCE

            return IntentAnalysis(
                intent=intent,
                confidence=1.0 if analysis_result.get("is_code_request") else 0.8,
                parameters={
                    "text": dialogue.text,
                    "type": dialogue.type.name,
                    "tags": dialogue.tags,
                    "is_code_request": analysis_result.get("is_code_request", False),
                    "code_details": analysis_result.get("code_details", {}),
                },
            )

        except json.JSONDecodeError:
            # 如果解析失败，返回基本的意图分析，视为无意义对话
            return IntentAnalysis(
                intent="",
                confidence=0.1,
                parameters={"text": dialogue.text, "type": dialogue.type.name, "tags": dialogue.tags, "reason": "解析失败"},
            )

    def _get_mime_type(self, file_path: str) -> str:
        """根据文件路径获取MIME类型"""
        extension = file_path.lower().split(".")[-1]
        return EXT_TO_MIME_TYPE.get(extension, "text/plain")

    def analyze_context(self, dialogue: ProcessingDialogue, dialogue_pool: DialoguePool) -> Set[int]:
        """分析对话的上下文关联

        增强对代码生成请求的上下文分析：
        1. 识别相关的代码讨论
        2. 跟踪代码需求的变化
        3. 关联代码生成的上下文

        Args:
            dialogue: 要分析的对话
            dialogue_pool: 对话池

        Returns:
            Set[int]: 相关对话的索引集合
        """
        # 获取当前stage和前一个stage的对话
        current_stage = dialogue.context.stage_index if dialogue.context else None
        stage_dialogues = []

        if current_stage is not None:
            # 获取当前stage的对话（排除当前对话）
            stage_dialogues.extend([
                d
                for d in dialogue_pool.dialogues
                if d.context and d.context.stage_index == current_stage and d.dialogue_index != dialogue.dialogue_index
            ])

            # 如果当前stage > 1，则获取前一个stage的对话
            if current_stage > 1:
                stage_dialogues.extend([
                    d for d in dialogue_pool.dialogues if d.context and d.context.stage_index == current_stage - 1
                ])

        # 准备上下文分析的输入数据
        context_inputs = ContextAnalysisInputs(
            opera_id=dialogue.opera_id,
            dialogue_index=dialogue.dialogue_index,
            text=dialogue.text,
            type=dialogue.type.name,
            tags=dialogue.tags if dialogue.tags else [],
            stage_index=dialogue.context.stage_index if dialogue.context else None,
            intent_analysis=dialogue.intent_analysis.intent if dialogue.intent_analysis else None,
            dialogue_same_stage=[
                {"index": d.dialogue_index, "text": d.text, "type": d.type.name, "tags": d.tags} for d in stage_dialogues[-10:]
            ],  # 只取最近10条对话
        )

        # 记录LLM输入
        logger.info(
            f"[LLM Input] Context Analysis Task for dialogue {dialogue.dialogue_index}:\n{context_inputs.model_dump_json()}"
        )

        # 执行分析
        context_crew = ContextAnalyzerCrew()
        result = context_crew.crew().kickoff(inputs=context_inputs)

        # 记录LLM输出
        logger.info(f"[LLM Output] Context Analysis Result for dialogue {dialogue.dialogue_index}:\n{result.raw}")

        try:
            # 使用ApiResponseParser解析结果
            context_data = ApiResponseParser.parse_crew_output(result)

            # 如果返回的是字符串，尝试解析为字典
            if isinstance(context_data, str):
                try:
                    # 移除可能的Markdown代码块标记
                    json_str = context_data.strip()
                    if json_str.startswith("```json\n"):
                        json_str = json_str[8:]
                    if json_str.endswith("\n```"):
                        json_str = json_str[:-4]
                    context_data = json.loads(json_str)
                except json.JSONDecodeError:
                    print("无法解析上下文数据结构")
                    return set()

            if not isinstance(context_data, dict):
                print("解析结果不是有效的字典结构")
                return set()

            # 验证必要的字段
            required_fields = ["conversation_flow", "code_context", "decision_points"]
            if not all(field in context_data for field in required_fields):
                raise ValueError("上下文数据结构缺少必要字段")

            # 验证主题相关字段
            flow = context_data["conversation_flow"]
            if not all(field in flow for field in ["topic_id", "topic_type", "current_topic"]):
                raise ValueError("conversation_flow缺少主题相关字段")

            # 更新conversation_state
            dialogue.context.conversation_state.update({
                "flow": flow,
                "code_context": context_data["code_context"],
                "decision_points": context_data["decision_points"],
                "topic": {
                    "id": flow["topic_id"],
                    "type": flow["topic_type"],
                    "name": flow["current_topic"],
                },
            })

            # 从decision_points中提取相关的对话索引，同时考虑主题关联
            related_indices = {
                int(point["dialogue_index"])
                for point in context_data["decision_points"]
                if "dialogue_index" in point
                and str(point["dialogue_index"]).isdigit()
                and point.get("topic_id") == flow["topic_id"]  # 确保只关联同一主题的对话
            }

            # 直接更新对话的相关索引
            dialogue.context.related_dialogue_indices = list(related_indices)

        except (ValueError, KeyError, AttributeError) as e:
            print(f"解析上下文数据结构失败: {str(e)}")
            return set()

        return related_indices
