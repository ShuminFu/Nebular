from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import Field

from Opera.FastAPI.models import CamelBaseModel
from Opera.core.api_response_parser import ApiResponseParser
from Opera.core.dialogue.enums import DialoguePriority, DialogueType, ProcessingStatus
from Opera.signalr_client.opera_signalr_client import MessageReceivedArgs
from ai_core.tools.opera_api.dialogue_api_tool import _SHARED_DIALOGUE_TOOL


class DialogueContext(CamelBaseModel):
    """对话上下文模型"""
    stage_index: Optional[int] = Field(default=None, description="对话阶段索引")
    related_dialogue_indices: List[int] = Field(
        default_factory=list, description="相关对话索引列表")
    conversation_state: Dict[str, Any] = Field(
        default_factory=dict, description="对话状态信息比如Pending Task来表述依赖顺序关系，暂时无用")


class IntentAnalysis(CamelBaseModel):
    """意图分析结果模型"""
    intent: str = Field(..., description="识别出的意图描述")
    confidence: float = Field(..., description="置信度")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="提取的参数")


class ProcessingDialogue(CamelBaseModel):
    """处理中的对话模型

    基于SignalR客户端中接收到的的MessageReceivedArgs，添加了处理相关的属性和状态。
    用于跟踪和管理对话的处理过程。
    """

    def __init__(self, **data):
        # 处理 text 参数
        if 'text' in data:
            data['text_content'] = data.pop('text')
        super().__init__(**data)

    # 基础对话信息
    dialogue_index: int = Field(..., description="对话索引")
    created_at: datetime = Field(default_factory=lambda: datetime.now(
        timezone(timedelta(hours=8))), description="创建时间 (UTC+8)")
    sender_staff_id: Optional[UUID] = Field(
        default=None, description="发送者Staff ID")
    receiver_staff_ids: List[UUID] = Field(
        default_factory=list, description="接收者Staff ID列表")
    opera_id: UUID = Field(..., description="Opera ID")

    # 对话属性
    text_content: Optional[str] = Field(
        default=None, description="对话内容（私有，通过属性访问）")
    is_narratage: bool = Field(default=False, description="是否为旁白")
    is_whisper: bool = Field(default=False, description="是否为悄悄话")
    tags: Optional[str] = Field(default=None, description="标签")
    mentioned_staff_ids: List[UUID] = Field(
        default_factory=list, description="提及的Staff ID列表")

    def _fetch_text_from_api(self) -> str:
        """从API获取对话内容

        使用共享的DialogueTool实例获取指定opera_id和dialogue_index的对话内容。

        Returns:
            str: 对话内容。如果获取失败则返回空字符串。
        """
        try:
            # 准备API调用参数
            params = {
                "action": "get",
                "opera_id": self.opera_id,
                "dialogue_index": self.dialogue_index
            }

            # 使用共享的DialogueTool实例调用API
            result = _SHARED_DIALOGUE_TOOL.run(**params)

            # 使用ApiResponseParser解析响应
            status_code, data = ApiResponseParser.parse_response(result)

            # 返回对话文本内容
            if isinstance(data, dict) and "text" in data:
                return data["text"]

            # 如果无法获取内容，返回空字符串
            return ""

        except Exception as e:
            # 记录错误并返回空字符串
            print(f"获取对话内容失败: {str(e)}")
            return ""

    @property
    def text(self) -> str:
        """延迟加载对话内容

        Returns:
            str: 对话内容
        """
        if self.text_content is None:
            self.text_content = self._fetch_text_from_api()
        return self.text_content

    @text.setter
    def text(self, value: str) -> None:
        """设置对话内容

        Args:
            value: 对话内容
        """
        self.text_content = value

    # 处理属性
    priority: DialoguePriority = Field(
        default=DialoguePriority.NORMAL, description="处理优先级")
    type: DialogueType = Field(..., description="对话类型")
    status: ProcessingStatus = Field(
        default=ProcessingStatus.PENDING, description="处理状态")

    # 分析和上下文
    intent_analysis: Optional[IntentAnalysis] = Field(
        default=None, description="意图分析结果")
    context: DialogueContext = Field(
        default_factory=DialogueContext, description="对话上下文")

    # 错误处理
    retry_count: int = Field(default=0, description="重试次数")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    last_retry_at: Optional[datetime] = Field(
        default=None, description="最后重试时间")

    # 添加热度和过期相关属性
    heat: float = Field(default=1.0, description="对话热度，影响保留优先级")
    reference_count: int = Field(default=0, description="被引用次数")

    def update_heat(self, delta: float = 0.1) -> None:
        """更新对话热度

        Args:
            delta: 热度变化值，正数表示增加，负数表示减少
        """
        self.heat = max(0.0, self.heat + delta)
        if delta > 0:
            self.reference_count += 1

    def calculate_priority_score(self) -> float:
        """计算对话的优先级分数

        基于热度、引用次数和原始优先级计算最终分数
        分数越高表示越应该保留
        """
        # 引用次数影响优先级，但避免过度影响
        reference_factor = min(1.0 + (self.reference_count / 10.0), 2.0)
        return self.heat * reference_factor * float(self.priority)

    @classmethod
    def from_message_args(cls, message_args: MessageReceivedArgs,
                          priority: DialoguePriority = DialoguePriority.NORMAL,
                          dialogue_type: DialogueType = DialogueType.NORMAL) -> "ProcessingDialogue":
        """从MessageReceivedArgs创建ProcessingDialogue

        Args:
            args: SignalR接收到的消息参数
            priority: 对话优先级，默认为NORMAL
            dialogue_type: 对话类型，默认为NORMAL

        Returns:
            ProcessingDialogue: 处理中的对话对象
        """
        return cls(
            # 基础信息
            dialogue_index=message_args.index,
            created_at=message_args.time,
            sender_staff_id=message_args.sender_staff_id,
            receiver_staff_ids=message_args.receiver_staff_ids,
            opera_id=message_args.opera_id,

            # 对话属性
            text_content=message_args.text,
            is_narratage=message_args.is_narratage,
            is_whisper=message_args.is_whisper,
            tags=message_args.tags,
            mentioned_staff_ids=message_args.mentioned_staff_ids or [],

            # 处理属性
            priority=priority,
            type=dialogue_type,
            status=ProcessingStatus.PENDING,

            # 上下文
            context=DialogueContext(
                stage_index=message_args.stage_index,
                related_dialogue_indices=[],  # 初始为空，后续可能需要更新
                conversation_state={}  # 初始为空，后续可能需要更新
            )
        )


class PersistentDialogueState(ProcessingDialogue):
    """持久化的对话状态模型

    继承自ProcessingDialogue，但只保留需要持久化的关键状态信息。
    其他信息可以通过API重新获取。
    """
    class Config:
        # 只包含显式声明的字段
        extra = "forbid"

    # 对话标识（必需）
    dialogue_index: int = Field(..., description="对话索引")
    opera_id: UUID = Field(..., description="Opera的UUID")
    receiver_staff_ids: List[UUID] = Field(
        default_factory=list, description="接收者Staff ID列表")

    # 意图识别处理结果（必需）
    priority: DialoguePriority = Field(..., description="处理优先级")
    type: DialogueType = Field(..., description="对话类型")
    intent_analysis: Optional[IntentAnalysis] = Field(
        default=None, description="意图分析结果")
    context: DialogueContext = Field(
        default_factory=DialogueContext, description="对话上下文")

    # 对话池状态信息（必需）
    status: ProcessingStatus = Field(
        default=ProcessingStatus.PENDING, description="处理状态")
    heat: float = Field(default=1.0, description="对话热度")
    reference_count: int = Field(default=0, description="被引用次数")

    @classmethod
    def from_processing_dialogue(cls, dialogue: ProcessingDialogue) -> "PersistentDialogueState":
        """从ProcessingDialogue创建持久化状态"""
        return cls(
            dialogue_index=dialogue.dialogue_index,
            opera_id=dialogue.opera_id,
            receiver_staff_ids=dialogue.receiver_staff_ids,
            priority=dialogue.priority,
            type=dialogue.type,
            intent_analysis=dialogue.intent_analysis,
            context=dialogue.context,
            status=dialogue.status,
            heat=dialogue.heat,
            reference_count=dialogue.reference_count
        )

    def to_processing_dialogue(self) -> ProcessingDialogue:
        """将持久化状态转换为ProcessingDialogue对象

        Returns:
            ProcessingDialogue: 转换后的对话对象
        """
        return ProcessingDialogue(
            dialogue_index=self.dialogue_index,
            opera_id=self.opera_id,
            receiver_staff_ids=self.receiver_staff_ids,
            priority=self.priority,
            type=self.type,
            intent_analysis=self.intent_analysis,
            context=self.context,
            status=self.status,
            heat=self.heat,
            reference_count=self.reference_count
        )
