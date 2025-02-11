import json
from typing import Set

from crewai import Agent, Task, Crew

from src.core.dialogue.enums import DialogueType, EXT_TO_MIME_TYPE
from src.core.dialogue.models import ProcessingDialogue, IntentAnalysis
from src.crewai_ext.config.llm_setup import llm
from src.crewai_ext.tools.opera_api.dialogue_api_tool import _SHARED_DIALOGUE_TOOL
from src.crewai_ext.tools.utils.utility_tools import UUIDGeneratorTool
from src.core.dialogue.pools import DialoguePool
from src.core.api_response_parser import ApiResponseParser
from src.core.logger_config import get_logger
from src.core.dialogue.output_json_models import (
    IntentAnalysisResult,
    ContextStructure,
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

    def __init__(self):
        """初始化对话分析器"""
        # 创建意图分析Agent
        self.intent_analyzer = Agent(
            name="意图分析专家",
            role="对话意图分析专家",
            goal="准确识别和描述对话意图，能判断代码生成请求",
            backstory="""你是一个专业的对话意图分析专家，擅长：
            1. 从对话内容中识别出说话者的真实意图
            2. 用简洁的语言描述意图
            3. 理解对话的上下文关系
            4. 识别代码生成请求
            5. 分析代码相关任务
            6. 无论如何，所有true, false都请你使用字符串表示或者使用双引号包括起来，比如"True","False"

            在描述意图时，你应该：
            1. 使用简洁的语言
            2. 包含关键动作和目标
            3. 如果是工具调用，说明调用的工具
            4. 如果是任务相关，说明任务类型
            5. 对于代码生成请求：
               - 识别请求的代码类型（如Python,JAVA, JavaScript, HTML, CSS等）
               - 确定代码的用途和功能
               - 识别关键需求和约束
               - 标注是否需要特定的框架或库
            """,
            tools=[_SHARED_DIALOGUE_TOOL],
            verbose=True,
            llm=llm
        )

        # 创建上下文分析Agent
        self.context_analyzer = Agent(
            name="上下文关联专家",
            role="上下文关联专家",
            goal="分析对话间的关联性和上下文依赖",
            backstory="""你是一个专业的对话上下文分析专家，擅长：
            1. 识别对话之间的关联关系
            2. 构建对话的上下文依赖图
            3. 确保Opera之间的信息隔离
            4. 跟踪代码生成的上下文
            5. 在使用工具的过程中，无论如何记住重点，所有true, false都请你使用字符串表示或者使用双引号包括起来，比如"True","False"
            """,
            tools=[_SHARED_DIALOGUE_TOOL, UUIDGeneratorTool()],
            verbose=True,
            llm=llm,
        )

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
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # 创建意图分析任务
        task = Task(
            description=f"""分析以下对话的意图，判断是否是有意义的对话：

            对话信息：
            1. 内容：{dialogue.text}
            2. 类型：{dialogue.type.name}
            3. 是否为旁白：{dialogue.is_narratage}
            4. 是否为悄悄话：{dialogue.is_whisper}
            5. 标签：{dialogue.tags}
            6. 是否提及其他Staff：{bool(dialogue.mentioned_staff_ids)}

            要求：
            1. 首先判断对话是否有实质内容：
               - 是否包含明确的意图或目的
               - 是否需要响应或处理
               - 是否包含实质性的内容
               - 如果是纯粹的表情、语气词或无意义的重复，返回空字符串作为意图

            2. 如果对话有意义：
               - 用一句简洁的话描述意图
               - 包含关键动作和目标
               - 如果是工具调用，说明调用的工具
               - 如果是任务相关，说明任务类型

            3. 如果是代码生成请求：
               - 说明需要生成的代码类型（如Python, HTML, CSS等）
               - 描述代码的用途和功能
               - 列出关键需求和约束
               - 标注是否需要特定的框架或库
               - 识别需要生成的所有文件
               - 确定每个文件的类型和用途
               - 识别文件之间的关联（如HTML引用CSS和JS）
               - 确定项目的整体结构
               - is_code_request字段返回true
            4. 如果是已经生成了代码：
               - 比如parameters的text字段中已经生成了代码或者其他资源，则is_code_request字段返回false
               - 根据生成的代码中parameters的text字段中的头部信息获取file_path和mime_type用于返回的code_details.resrouces里。

            返回格式示例（JSON）：
            {{
                "intent": "意图描述，无意义对话则返回空字符串",
                "reason": "如果intent为空，说明原因",
                "is_code_request": true/false,
                "code_details": {{
                    "project_type": "web/python/java等项目类型",
                    "project_description": "项目整体描述",
                    "resources": [
                        {{
                            "file_path": "version_{timestamp}/src/html/index.html",
                            "type": "html",
                            "mime_type": "text/html",
                            "description": "主页面文件",
                            "references": ["style.css", "main.js"]
                        }},
                        {{
                            "file_path": "version_{timestamp}/src/css/style.css",
                            "type": "css",
                            "mime_type": "text/css",
                            "description": "样式文件"
                        }},
                        {{
                            "file_path": "version_{timestamp}/src/js/main.js",
                            "type": "javascript",
                            "mime_type": "text/javascript",
                            "description": "交互脚本"
                        }}
                    ],
                    "requirements": ["需求1", "需求2"],
                    "frameworks": ["react", "vue", "@popperjs/core", "normalize.css"]
                }}
            }}

            注意：
            1. 对于前端项目，需要生成完整的文件结构
            2. 对于后端项目，需要包含必要的配置文件
            3. 文件路径要符合项目最佳实践
            4. MIME类型必须准确
            """,
            expected_output="按照IntentAnalysisResult模型的格式返回JSON结果，如果是无意义的对话则intent字段返回空字符串, 文件名要考虑context中的项目结构信息, 包含意图描述、原因说明、是否为代码请求等信息",
            agent=self.intent_analyzer,
            output_json=IntentAnalysisResult
        )
        logger.info(f"[LLM Input] Intent Analysis Task for dialogue {dialogue.dialogue_index}:\n{task.description}")

        # 执行分析
        crew = Crew(
            agents=[self.intent_analyzer],
            tasks=[task],
            verbose=True
        )
        result = crew.kickoff()

        # 记录LLM输出
        logger.info(f"[LLM Output] Intent Analysis Result for dialogue {dialogue.dialogue_index}:\n{result.raw}")

        try:
            # 解析结果
            result_str = result.raw
            # 移除可能的Markdown代码块标记
            if result_str.startswith('```json\n'):
                result_str = result_str[8:]
            if result_str.endswith('\n```'):
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
                        "reason": analysis_result.get("reason", "无实质性内容")
                    }
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
                    *[f"framework_{f.lower()}" for f in frameworks]  # 添加框架标签
                ]

                # 更新对话标签
                if dialogue.tags:
                    dialogue.tags = f"{dialogue.tags},{','.join(code_tags)}"
                else:
                    dialogue.tags = ','.join(code_tags)

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
                    "code_details": analysis_result.get("code_details", {})
                }
            )

        except json.JSONDecodeError:
            # 如果解析失败，返回基本的意图分析，视为无意义对话
            return IntentAnalysis(
                intent="",
                confidence=0.1,
                parameters={
                    "text": dialogue.text,
                    "type": dialogue.type.name,
                    "tags": dialogue.tags,
                    "reason": "解析失败"
                }
            )

    def _get_mime_type(self, file_path: str) -> str:
        """根据文件路径获取MIME类型"""
        extension = file_path.lower().split('.')[-1]
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
                d for d in dialogue_pool.dialogues
                if d.context and d.context.stage_index == current_stage
                and d.dialogue_index != dialogue.dialogue_index
            ])

            # 如果当前stage > 1，则获取前一个stage的对话
            if current_stage > 1:
                stage_dialogues.extend([
                    d for d in dialogue_pool.dialogues
                    if d.context and d.context.stage_index == current_stage - 1
                ])

        # 创建上下文分析任务
        index_task = Task(
            description=f"""不使用工具，分析以下对话的上下文关联，关注代码生成相关的上下文：

            当前对话：
            - Opera ID: {dialogue.opera_id}
            - 索引：{dialogue.dialogue_index}
            - 内容：{dialogue.text}
            - 类型：{dialogue.type.name}
            - 标签：{dialogue.tags}
            - 阶段：{dialogue.context.stage_index if dialogue.context else None}

            同阶段的对话：
            {[f"- 索引：{d.dialogue_index}, 内容：{d.text}" for d in stage_dialogues[-10:]]}

            分析要求：
            1. 识别相关的代码讨论
            2. 跟踪代码需求的变化
            3. 关联代码生成的上下文
            4. 考虑时序关系
            5. 分析对话意图的关联
            6. 优先关联同一阶段的对话

            返回格式：逗号分隔的相关对话索引列表。如果没有相关对话，返回空字符串。
            """,
            expected_output="逗号分隔的相关对话DialogueIndex列表，例如：1,2,3",
            agent=self.context_analyzer
        )

        context_structure_task = Task(
            description=f"""使用对话工具的get action来分析相关对话并生成结构化的上下文数据：

            当前对话：
            - Opera ID: {dialogue.opera_id}
            - 索引：{dialogue.dialogue_index}
            - 内容：{dialogue.text}
            - 类型：{dialogue.type.name}
            - 标签：{dialogue.tags}
            - 意图：{dialogue.intent_analysis.intent if dialogue.intent_analysis else None}

            相关对话：基于前一个任务得到的索引列表

            分析要求：
            1. 提取对话主题和关键信息
            2. 识别对话流程和状态变化
            3. 跟踪重要的上下文变量
            4. 记录关键的决策点
            5. 特别关注代码生成相关的上下文：
               - 代码需求的演变
               - API和框架的选择
               - 文件结构的变化
               - 重要的配置决定
            6. 主题定义规则：
                1. 主题独立性：
                - 每个主题代表一个明确的目标或需求
                - 当需求发生变更时，应创建新主题，必要的时候使用工具创建UUID
                - 新主题应该关联到源主题

                2. 变更判断标准：
                - 功能需求的重大改变
                - 架构或设计的显著调整
                - 技术栈或依赖的变更
                - 与原主题目标的显著偏离

                3. 主题状态：
                - active: 当前正在处理的主题
                - completed: 已完成的主题
                - superseded: 被新主题取代的主题

            返回格式（JSON）：
    {{
        "conversation_flow": {{
            "current_topic": "当前主题名称",
            "topic_id": "主题UUID",
            "topic_type": "主题类型（如 code_generation, requirement_discussion 等）",
            "status": "主题状态（active/completed/superseded）",
            "created_at": "主题创建时间",
            "derived_from": "源主题ID",
            "change_reason": "如果是衍生主题，记录变更原因",
            "evolution_chain": ["topic-id-1", "topic-id-2"],
            "previous_topics": ["历史主题"]
        }},
        "code_context": {{
            "requirements": ["需求列表"],
            "frameworks": ["使用的框架"],
            "file_structure": ["文件结构"],
            "api_choices": ["API选择"],
        }},
        "decision_points": [
            {{
                "decision": "决策内容",
                "reason": "决策原因",
                "dialogue_index": "相关对话索引",
                "topic_id": "主题ID"
            }}
        ]
    }}
            """,
            expected_output="返回符合ContextStructure模型的JSON结构，包含对话流程、代码上下文和决策点信息",
            agent=self.context_analyzer,
            output_json=ContextStructure,
        )

        # 记录LLM输入 - 索引任务
        logger.info(f"[LLM Input] Context Index Task for dialogue {dialogue.dialogue_index}:\n{index_task.description}")

        # 执行分析
        crew = Crew(
            agents=[self.context_analyzer],
            tasks=[index_task, context_structure_task],
            verbose=True
        )
        result = crew.kickoff()

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
                    if json_str.startswith('```json\n'):
                        json_str = json_str[8:]
                    if json_str.endswith('\n```'):
                        json_str = json_str[:-4]
                    context_data = json.loads(json_str)
                except json.JSONDecodeError:
                    print("无法解析上下文数据结构")
                    return set()

            if not isinstance(context_data, dict):
                print("解析结果不是有效的字典结构")
                return set()

            # 验证必要的字段
            required_fields = ['conversation_flow', 'code_context', 'decision_points']
            if not all(field in context_data for field in required_fields):
                raise ValueError("上下文数据结构缺少必要字段")

            # 验证主题相关字段
            flow = context_data["conversation_flow"]
            if not all(field in flow for field in ['topic_id', 'topic_type', 'current_topic']):
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
                }
            })

            # 从decision_points中提取相关的对话索引，同时考虑主题关联
            related_indices = {
                int(point["dialogue_index"])
                for point in context_data["decision_points"]
                if "dialogue_index" in point and str(point["dialogue_index"]).isdigit()
                and point.get("topic_id") == flow["topic_id"]  # 确保只关联同一主题的对话
            }

            # 直接更新对话的相关索引
            dialogue.context.related_dialogue_indices = list(related_indices)

        except (ValueError, KeyError, AttributeError) as e:
            print(f"解析上下文数据结构失败: {str(e)}")
            return set()

        return related_indices
