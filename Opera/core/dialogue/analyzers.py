import json
from typing import Set

from crewai import Agent, Task, Crew

from Opera.core.dialogue.enums import DialogueType
from Opera.core.dialogue.models import ProcessingDialogue, IntentAnalysis
from ai_core.configs.config import llm
from ai_core.tools.opera_api.dialogue_api_tool import _SHARED_DIALOGUE_TOOL
from Opera.core.dialogue.pools import DialoguePool

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
            4. 确保信息安全，不会泄露跨Opera的信息
            5. 识别代码生成请求
            6. 分析代码相关任务

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
            4. 维护对话的时序关系
            5. 跟踪代码生成的上下文
            """,
            # tools=[_SHARED_DIALOGUE_TOOL],
            verbose=True,
            llm=llm
        )

    def analyze_intent(self, dialogue: ProcessingDialogue) -> IntentAnalysis:
        """分析单个对话的意图

        能判断对代码生成请求的识别：
        1. 识别是否是代码生成请求
        2. 提取代码类型和要求
        3. 分析代码生成的上下文
        4. 识别并过滤无意义对话

        Args:
            dialogue: 要分析的对话

        Returns:
            IntentAnalysis: 意图分析结果，对于无意义对话，intent为空字符串，confidence为0.1
        """
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

            返回格式示例（JSON）：
            {{
                "intent": "意图描述，无意义对话则返回空字符串",
                "reason": "如果intent为空，说明原因",
                "is_code_request": true/false,
                "code_details": {{  # 仅在is_code_request为true时需要
                    "file_path": "src/xxx.py",
                    "type": "代码类型",
                    "purpose": "用途描述",
                    "requirements": ["需求1", "需求2"],
                    "frameworks": ["框架1", "框架2"]
                }}
            }}
            """,
            expected_output="描述对话意图，包含动作和目标的JSON，如果是无意义的对话则intent字段返回空字符串, 文件名要考虑context中的项目结构信息",
            agent=self.intent_analyzer
        )

        # 执行分析
        crew = Crew(
            agents=[self.intent_analyzer],
            tasks=[task],
            verbose=True
        )
        result = crew.kickoff()

        # 解析结果
        try:
            # 从CrewOutput中提取JSON字符串
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

            # 如果是代码生成请求，添加特殊标记
            if analysis_result.get("is_code_request"):
                code_details = analysis_result.get("code_details", {})
                code_type = code_details.get("type", "").lower()

                # 更新对话标签
                code_tags = [
                    "code_request",  # 标记这是一个代码生成请求
                    f"code_type_{code_type}",  # 代码类型标记
                    *[f"framework_{f.lower()}" for f in code_details.get("frameworks", [])]  # 框架标记
                ]

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

        # 获取同一Opera下的对话
        opera_dialogues = [
            d for d in dialogue_pool.dialogues
            if d.opera_id == dialogue.opera_id
        ]

        # 创建上下文分析任务
        task = Task(
            description=f"""分析以下对话的上下文关联，关注代码生成相关的上下文：

            当前对话：
            - 索引：{dialogue.dialogue_index}
            - 内容：{dialogue.text}
            - 类型：{dialogue.type.name}
            - 标签：{dialogue.tags}

            可能相关的对话：
            {[f"- 索引：{d.dialogue_index}, 内容：{d.text}" for d in opera_dialogues[-10:]]}

            分析要求：
            1. 识别相关的代码讨论
            2. 跟踪代码需求的变化
            3. 关联代码生成的上下文
            4. 考虑时序关系
            5. 分析对话意图的关联

            返回格式：逗号分隔的相关对话索引列表。如果没有相关对话，返回空字符串。
            """,
            expected_output="逗号分隔的相关对话DialogueIndex列表，例如：1,2,3",
            agent=self.context_analyzer
        )

        # 执行分析
        crew = Crew(
            agents=[self.context_analyzer],
            tasks=[task],
            verbose=True
        )
        result = crew.kickoff()

        # 解析结果，提取相关对话索引
        related_indices = set()
        try:
            # 从CrewOutput中提取实际的字符串内容
            if result and hasattr(result, 'raw'):
                # 如果raw是整数，直接添加到集合中
                if isinstance(result.raw, int):
                    related_indices.add(result.raw)
                else:
                    # 尝试解析为JSON或字符串
                    try:
                        import json
                        indices_str = json.loads(result.raw)
                        if isinstance(indices_str, int):
                            related_indices.add(indices_str)
                        elif isinstance(indices_str, str):
                            indices = [int(idx.strip()) for idx in indices_str.split(',')]
                            related_indices.update(indices)
                    except (json.JSONDecodeError, AttributeError):
                        # 如果不是JSON，直接使用raw值
                        indices_str = result.raw.strip('"')
                        if indices_str:
                            try:
                                if ',' in indices_str:
                                    indices = [int(idx.strip()) for idx in indices_str.split(',')]
                                    related_indices.update(indices)
                                else:
                                    related_indices.add(int(indices_str))
                            except ValueError:
                                pass
            elif isinstance(result, str):
                if ',' in result:
                    indices = [int(idx.strip()) for idx in result.split(',')]
                    related_indices.update(indices)
                else:
                    try:
                        related_indices.add(int(result))
                    except ValueError:
                        pass
        except (ValueError, AttributeError):
            pass

        return related_indices
