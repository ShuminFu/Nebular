from crewai.flow.flow import Flow, listen, start, router, or_, and_  # noqa
from typing import Dict, Set
from pydantic import BaseModel
from src.core.dialogue.enums import DialogueType
from src.core.dialogue.models import ProcessingDialogue, IntentAnalysis
from src.core.dialogue.pools import DialoguePool
from src.core.dialogue.enums import EXT_TO_MIME_TYPE
from src.crewai_ext.crew_bases.analyzers_crewbase import (
    IntentAnalyzerCrew,
    ContextAnalyzerCrew,
    IntentAnalysisInputs,
    ContextAnalysisInputs,
)
from src.crewai_ext.crew_bases.resource_iteration_crewbase import IterationAnalyzerCrew, IterationAnalysisInputs
from src.core.logger_config import get_logger, get_logger_with_trace_id
import json
from datetime import datetime, timezone, timedelta
import re

logger = get_logger(__name__, log_file="logs/analysis_flow.log")


# 在AnalysisFlow类之前添加状态模型
class AnalysisState(BaseModel):
    intent_flag: bool = False
    intent_analysis: IntentAnalysis = None
    related_indices: Set[int] = set()
    iteration_flag: bool = False


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
        self.iteration_crew = IterationAnalyzerCrew()
        self.log = get_logger_with_trace_id()

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
        # 判断对话类型决定使用哪个分析器
        if self.dialogue.type == DialogueType.ITERATION:
            # 使用迭代分析器
            self.state.iteration_flag = True

            # 解析tags中的资源信息
            resource_list = self._extract_resources_from_tags(self.dialogue.tags)

            # 准备迭代分析输入
            iteration_inputs = IterationAnalysisInputs(
                iteration_requirement=self.dialogue.text + f" opera id: {self.dialogue.opera_id}",
                resource_list=resource_list,
            )
            self.log.info(f"迭代分析输入: {iteration_inputs.model_dump()}")
            # 执行迭代分析
            result = await self.iteration_crew.crew().kickoff_async(inputs=iteration_inputs.model_dump())
        else:
            # 使用标准意图分析器
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
            self.log.info(f"意图分析输入: {intent_inputs.model_dump()}")
            # 执行意图分析
            result = await self.intent_crew.crew().kickoff_async(inputs=intent_inputs.model_dump())

        # 解析结果并更新对话的意图分析
        intent_analysis = self._parse_intent_result(result.raw)
        self.dialogue.intent_analysis = intent_analysis
        self.log.info(f"意图分析结果: {intent_analysis}")
        # 如果意图分析表明这是一个代码请求，更新对话类型
        if self.dialogue.intent_analysis and self.dialogue.intent_analysis.parameters.get("is_code_request"):
            self.dialogue.type = DialogueType.CODE_RESOURCE
            self.log.info(f"更新对话类型为: {self.dialogue.type}")
        # 将分析结果存储在Flow状态中
        self.state.intent_analysis = intent_analysis

        self.state.intent_flag = True

    def _extract_resources_from_tags(self, tags_str: str) -> list:
        """从tags字符串中提取资源信息

        Args:
            tags_str: tags字符串，可能是JSON格式

        Returns:
            list: 资源列表，格式为[{'file_path': 'path', 'resource_id': 'id'}]
        """
        try:
            # 尝试解析JSON
            tags_data = json.loads(tags_str)
            resources = []

            # 处理第一种格式: ResourcesForViewing
            if "ResourcesForViewing" in tags_data:
                viewing_data = tags_data["ResourcesForViewing"]
                # 处理Resources格式
                if "Resources" in viewing_data and isinstance(viewing_data["Resources"], list):
                    for resource in viewing_data["Resources"]:
                        if "Url" in resource and "ResourceId" in resource:
                            resources.append({"file_path": resource["Url"], "resource_id": resource["ResourceId"]})
                # 处理CurrentVersion格式 - 第四种格式
                elif "CurrentVersion" in viewing_data:
                    current_version = viewing_data["CurrentVersion"]

                    # 提取current_files信息
                    if "current_files" in current_version:
                        resources.extend(current_version["current_files"])
                    # 如果没有current_files，尝试提取modified_files
                    elif "modified_files" in current_version:
                        resources.extend(current_version["modified_files"])
            # 处理第二种格式: ResourcesMentionedFromViewer
            elif "ResourcesMentionedFromViewer" in tags_data and isinstance(tags_data["ResourcesMentionedFromViewer"], list):
                for resource_id in tags_data["ResourcesMentionedFromViewer"]:
                    resources.append({
                        "file_path": "",  # 空文件路径
                        "resource_id": resource_id,
                    })

            # 处理第三种格式: SelectedTextsFromViewer
            elif "SelectedTextsFromViewer" in tags_data and isinstance(tags_data["SelectedTextsFromViewer"], list):
                version_ids = []
                for selected_text in tags_data["SelectedTextsFromViewer"]:
                    if "VersionId" in selected_text:
                        version_ids.append(selected_text["VersionId"])

                # 添加递归保护机制
                if not getattr(self, "_processing_version_ids", None):
                    self._processing_version_ids = set()

                new_version_ids = [vid for vid in version_ids if vid not in self._processing_version_ids]
                if new_version_ids:
                    self._processing_version_ids.update(new_version_ids)
                    resources = self._get_resources_by_version_ids(new_version_ids)
                    self._processing_version_ids.difference_update(new_version_ids)
                else:
                    resources = []

            # 如果没有找到资源，或者解析失败，返回空列表
            if not resources and self.dialogue.mentioned_staff_ids:
                self.log.warning("从tags中提取资源失败，返回空列表")
                resources = []

            return resources

        except json.JSONDecodeError:
            self.log.warning(f"解析tags JSON失败: {tags_str}")
            return []

    def _get_resources_by_version_ids(self, version_ids: list) -> list:
        """根据版本ID获取资源信息

        通过Dialog API工具查找包含指定版本ID的对话，
        并从对话的ResourcesForViewing和CurrentVersion标签中提取资源信息

        Args:
            version_ids: 版本ID列表

        Returns:
            list: 资源列表，格式为[{'file_path': 'path', 'resource_id': 'id'}]
        """
        self.log.info(f"根据版本ID获取资源: {version_ids}")
        resources = []

        # 遍历每个版本ID查找相关对话
        for version_id in version_ids:
            if version_id in getattr(self, "_processing_version_ids", set()):
                self.log.warning(f"检测到递归循环，跳过版本ID {version_id}")
                continue

            # 构建查询条件，寻找包含指定VersionId的对话
            filter_data = {
                "action": "get_filtered",
                "opera_id": str(self.dialogue.opera_id),
                "data": {
                    "includes_staff_id_null": True,
                    "includes_stage_index_null": True,
                    "includes_narratage": True,
                    "tag_node_paths": ["$.ResourcesForViewing.VersionId"],
                    "tag_node_values": [{"path": "$.ResourcesForViewing.VersionId", "value": version_id, "type": "String"}],
                },
            }

            try:
                # 调用DialogueTool查询对话
                from crewai_ext.tools.opera_api.dialogue_api_tool import DialogueTool

                dialogue_tool = DialogueTool()
                result = dialogue_tool.run(**filter_data)

                # 解析返回结果
                if result:
                    dialogues = json.loads(result)
                    for dialogue in dialogues:
                        if "tags" in dialogue:
                            try:
                                # 使用_extract_resources_from_tags方法解析tags
                                extracted_resources = self._extract_resources_from_tags(dialogue["tags"])
                                if extracted_resources:
                                    resources.extend(extracted_resources)
                            except json.JSONDecodeError:
                                self.log.warning(f"解析对话tags失败: {dialogue['tags']}")
                                continue
            except Exception as e:
                self.log.error(f"查询版本ID为{version_id}的对话时出错: {str(e)}")
                continue

        # 去重，避免重复资源
        unique_resources = []
        resource_ids = set()

        for resource in resources:
            if resource.get("resource_id") and resource.get("resource_id") not in resource_ids:
                resource_ids.add(resource.get("resource_id"))
                unique_resources.append(resource)

        return unique_resources

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
        self.log.info(f"上下文分析输入: {context_inputs.model_dump()}")
        # 执行上下文分析
        result = await self.context_crew.crew().kickoff_async(inputs=context_inputs.model_dump())
        self.log.info(f"上下文分析结果: {result.raw}")
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
        try:
            # 清理和标准化输入字符串
            if result_str.startswith("```json\n"):
                result_str = result_str[8:]
            if result_str.endswith("\n```"):
                result_str = result_str[:-4]

            # 替换单引号为双引号，这可能导致JSON解析问题
            result_str = result_str.replace("'", '"')

            # 处理嵌套引号问题 - 非转义双引号替换为单引号
            # 找到未被转义的双引号（不是在字符串开始/结束处的）
            result_str = re.sub(r'([^\\])"([^"\\]*)"', r'\1"\2"', result_str)

            # 修复常见的JSON格式错误
            # 1. 移除多余的逗号（如数组或对象的末尾）
            result_str = re.sub(r",\s*([}\]])", r"\1", result_str)
            # 2. 确保所有属性名都有双引号
            result_str = re.sub(r"([{,])\s*([a-zA-Z0-9_]+)\s*:", r'\1"\2":', result_str)

            try:
                context_data = json.loads(result_str, strict=False)
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析错误: {str(e)}, 尝试使用替代方法解析")

                # 尝试更全面的清理
                try:
                    # 处理嵌套JSON中的引号问题
                    cleaned_str = result_str
                    # 替换所有非转义双引号的引号对，这通常是内部嵌套内容
                    cleaned_str = re.sub(r'(:\s*"[^"]*)"([^"]*)"([^"]*")', r"\1\'\2\'\3", cleaned_str)
                    context_data = json.loads(cleaned_str, strict=False)
                except json.JSONDecodeError:
                    logger.warning("第二次JSON解析尝试失败，使用ast.literal_eval")

                    try:
                        # 使用更宽松的解析方式，将单引号转回来以便ast.literal_eval处理
                        py_compatible_str = result_str.replace('"', "'")
                        # 修复Python字典键的引号
                        py_compatible_str = re.sub(r"([{,]\s*)([a-zA-Z0-9_]+)(\s*:)", r"\1'\2'\3", py_compatible_str)

                        import ast

                        context_data = ast.literal_eval(py_compatible_str)
                    except (SyntaxError, ValueError) as ast_error:
                        logger.error(f"ast.literal_eval解析失败: {str(ast_error)}")
                        # 最后尝试
                        try:
                            # 提取并修复所有可能的字段
                            pattern = r'"conversation_flow"\s*:\s*({[^}]+})'
                            flow_match = re.search(pattern, result_str)
                            flow_data = (
                                json.loads(flow_match.group(1))
                                if flow_match
                                else {"topic_id": "", "topic_type": "", "current_topic": ""}
                            )

                            # 尝试提取decision_points
                            pattern = r'"decision_points"\s*:\s*(\[[^\]]+\])'
                            decisions_match = re.search(pattern, result_str)
                            decision_points = []

                            if decisions_match:
                                try:
                                    decision_points = json.loads(decisions_match.group(1))
                                except (json.JSONDecodeError, ValueError, TypeError):
                                    # 手动提取每个对话索引
                                    index_pattern = r'"dialogue_index"\s*:\s*"(\d+)"'
                                    indices = re.findall(index_pattern, result_str)
                                    topic_id = flow_data.get("topic_id", "")
                                    decision_points = [{"dialogue_index": idx, "topic_id": topic_id} for idx in indices]

                            # 构建最少需要的数据结构
                            context_data = {
                                "conversation_flow": flow_data,
                                "code_context": {"requirements": [], "frameworks": [], "file_structure": []},
                                "decision_points": decision_points,
                            }
                        except Exception as final_error:
                            logger.error(f"所有解析方法都失败: {str(final_error)}")
                            raise ValueError("无法解析上下文数据")

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
            related_indices = set()
            for point in context_data["decision_points"]:
                if "dialogue_index" in point:
                    try:
                        # 尝试转换为整数
                        idx = int(point["dialogue_index"])
                        if point.get("topic_id") == flow["topic_id"]:  # 确保只关联同一主题的对话
                            related_indices.add(idx)
                    except (ValueError, TypeError):
                        logger.warning(f"无法解析对话索引: {point['dialogue_index']}")

            # 更新对话的相关索引
            self.dialogue.context.related_dialogue_indices = list(related_indices)

            return related_indices

        except (ValueError, KeyError, AttributeError, TypeError) as e:
            logger.error(f"解析上下文数据结构失败: {str(e)}")
            logger.debug(f"原始结果字符串: {result_str}")
            return set()
        except Exception as e:
            logger.error(f"解析过程中发生未预期的错误: {str(e)}")
            logger.debug(f"原始结果字符串: {result_str}")
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
