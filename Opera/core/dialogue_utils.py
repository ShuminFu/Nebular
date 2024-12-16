"""Opera SignalR 对话队列的数据模型定义。"""

from pydantic import Field 
from typing import List, Optional, Dict, Any, Set
from datetime import datetime, timezone, timedelta
from uuid import UUID
from enum import IntEnum
from collections import Counter
import heapq

from Opera.signalr_client.opera_signalr_client import MessageReceivedArgs
from Opera.FastAPI.models import CamelBaseModel, Dialogue


class DialoguePriority(IntEnum):
    """对话优先级枚举"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


class DialogueType(IntEnum):
    """对话类型枚举"""
    TEXT = 1
    COMMAND = 2
    QUERY = 3
    SYSTEM = 4


class ProcessingStatus(IntEnum):
    """处理状态枚举"""
    PENDING = 1
    PROCESSING = 2
    COMPLETED = 3
    FAILED = 4


class DialogueContext(CamelBaseModel):
    """对话上下文模型"""
    stage_index: Optional[int] = Field(default=None, description="对话阶段索引")
    related_dialogue_indices: List[int] = Field(default_factory=list, description="相关对话索引列表")
    conversation_state: Dict[str, Any] = Field(default_factory=dict, description="对话状态信息")


class IntentAnalysis(CamelBaseModel):
    """意图分析结果模型"""
    intent: str = Field(..., description="识别出的意图")
    confidence: float = Field(..., description="置信度")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="提取的参数")


class ProcessingDialogue(CamelBaseModel):
    """处理中的对话模型
    
    扩展了原始Dialogue，添加了处理相关的属性和状态。
    用于跟踪和管理对话的处理过程。
    """
    # 基础对话信息
    dialogue_index: int = Field(..., description="对话索引")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone(timedelta(hours=8))), description="创建时间 (UTC+8)")
    staff_id: Optional[UUID] = Field(default=None, description="发送者Staff ID")
    
    # 对话属性
    _text: Optional[str] = Field(default=None, description="对话内容（私有，通过属性访问）")
    is_narratage: bool = Field(default=False, description="是否为旁白")
    is_whisper: bool = Field(default=False, description="是否为悄悄话")
    tags: Optional[str] = Field(default=None, description="标签")
    mentioned_staff_ids: List[UUID] = Field(default_factory=list, description="提及的Staff ID列表")
    
    def _fetch_text_from_api(self) -> str:
        """从API获取话内容的占位方法
        
        Returns:
            str: 对话内容
        
        TODO: _fetch_text_from_api 实现实际的API调用逻辑
        """
        # 这里后续需要实现实际的API调用
        # 临时返回占位内容
        return f"Dialogue content for index: {self.dialogue_index}"
    
    @property
    def text(self) -> str:
        """延迟加载对话内容
        
        Returns:
            str: 对话内容
        """
        if self._text is None:
            self._text = self._fetch_text_from_api()
        return self._text
    
    @text.setter
    def text(self, value: str) -> None:
        """设置对话内容
        
        Args:
            value: 对话内容
        """
        self._text = value
    
    # 处理属性
    priority: DialoguePriority = Field(default=DialoguePriority.NORMAL, description="处理优先级")
    type: DialogueType = Field(..., description="对话类型")
    status: ProcessingStatus = Field(default=ProcessingStatus.PENDING, description="处理状态")
    
    # 分析和上下文
    intent_analysis: Optional[IntentAnalysis] = Field(default=None, description="意图分析结果")
    context: DialogueContext = Field(default_factory=DialogueContext, description="对话上下文")
    
    # 错误处理
    retry_count: int = Field(default=0, description="重试次数")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    last_retry_at: Optional[datetime] = Field(default=None, description="最后重试时间")
    
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
    def from_dialogue(cls, dialogue: Dialogue, 
                     priority: DialoguePriority = DialoguePriority.NORMAL,
                     dialogue_type: DialogueType = DialogueType.TEXT) -> "ProcessingDialogue":
        """从原始Dialogue创建ProcessingDialogue
        
        Args:
            dialogue: 原始对话
            priority: 对话优先级，默认为NORMAL
            dialogue_type: 对话类型，默认为TEXT
            
        Returns:
            ProcessingDialogue: 处理中的对话对象
        """
        return cls(
            # 基础信息
            dialogue_index=dialogue.index,
            created_at=dialogue.time,
            staff_id=dialogue.staff_id,
            
            # 对话属性
            _text=dialogue.text,
            is_narratage=dialogue.is_narratage,
            is_whisper=dialogue.is_whisper,
            tags=dialogue.tags,
            mentioned_staff_ids=dialogue.mentioned_staff_ids or [],
            
            # 处理属性
            priority=priority,
            type=dialogue_type,
            status=ProcessingStatus.PENDING,
            
            # 上下文
            context=DialogueContext(
                stage_index=dialogue.stage_index,
                related_dialogue_indices=[],  # 初始为空，后续可能需要更新
                conversation_state={}  # 初始为空，后续可能需要更新
            )
        )

    @classmethod
    def from_message_args(cls, args: MessageReceivedArgs,
                     priority: DialoguePriority = DialoguePriority.NORMAL,
                     dialogue_type: DialogueType = DialogueType.TEXT) -> "ProcessingDialogue":
        """从MessageReceivedArgs创建ProcessingDialogue
        
        Args:
            args: SignalR接收到的消息参数
            priority: 对话优先级，默认为NORMAL
            dialogue_type: 对话类型，默认为TEXT
            
        Returns:
            ProcessingDialogue: 处理中的对话对象
        """
        return cls(
            # 基础信息
            dialogue_index=args.index,
            created_at=args.time,
            staff_id=args.sender_staff_id,
            
            # 对话属性
            _text=args.text,
            is_narratage=args.is_narratage,
            is_whisper=args.is_whisper,
            tags=args.tags,
            mentioned_staff_ids=args.mentioned_staff_ids or [],
            
            # 处理属性
            priority=priority,
            type=dialogue_type,
            status=ProcessingStatus.PENDING,
            
            # 上下文
            context=DialogueContext(
                stage_index=args.stage_index,
                related_dialogue_indices=[],  # 初始为空，后续可能需要更新
                conversation_state={}  # 初始为空，后续可能需要更新
            )
        )


class DialoguePool(CamelBaseModel):
    """对话池模型
    
    管理和追踪所有处理中的对话。
    提供对话状态管理和统计功能。
    """
    dialogues: List[ProcessingDialogue] = Field(default_factory=list, description="处理中的对话列表")
    status_counter: Dict[str, int] = Field(
        default_factory=lambda: {status.name.lower(): 0 for status in ProcessingStatus},
        description="状态计数器"
    )
    
    # 配置参数
    max_size: int = Field(default=1000, description="对话池最大容量")
    min_heat_threshold: float = Field(default=0.5, description="最小热度阈值")
    heat_decay_rate: float = Field(default=0.1, description="每次维护时的热度衰减率")
    max_age_hours: int = Field(default=24, description="对话最大保留时间（小时）")
    
    def _decay_heat(self) -> None:
        """对所有对话进行热度衰减
        
        热度衰减与时间无关，只与维护频率相关
        """
        for dialogue in self.dialogues:
            # 热度随着每次维护自然衰减
            dialogue.update_heat(-self.heat_decay_rate)
    
    def _clean_expired_dialogues(self) -> None:
        """清理过期对话
        
        基于对话创建时间进行清理，与热度机制独立
        """
        now = datetime.now(timezone(timedelta(hours=8)))
        max_age = timedelta(hours=self.max_age_hours)
        
        # 保留未过期的对话
        old_count = len(self.dialogues)
        self.dialogues = [
            d for d in self.dialogues
            if (now - d.created_at) <= max_age
        ]
        
        # 更新状态计数器
        if old_count != len(self.dialogues):
            # 重新计算状态计数
            self.status_counter = Counter(d.status.name.lower() for d in self.dialogues)
    
    def _clean_cold_dialogues(self) -> None:
        """清理冷对话（热度低于阈值）"""
        self.dialogues = [
            d for d in self.dialogues
            if d.heat >= self.min_heat_threshold
        ]
    
    def _enforce_size_limit(self) -> None:
        """强制执行大小限制
        
        如果对话池超过最大容量，删除优先级最低的对话
        """
        if len(self.dialogues) <= self.max_size:
            return
            
        # 计算所有对话的优先级分数
        scored_dialogues = [
            (-d.calculate_priority_score(), i, d)
            for i, d in enumerate(self.dialogues)
        ]
        
        # 使用堆排序找出要保留的对话
        heapq.heapify(scored_dialogues)
        keep_dialogues = []
        for _ in range(self.max_size):
            if scored_dialogues:
                _, _, dialogue = heapq.heappop(scored_dialogues)
                keep_dialogues.append(dialogue)
        
        self.dialogues = keep_dialogues
    
    def maintain_pool(self) -> None:
        """维护对话池
        
        1. 清理过期对话（基于时间）
        2. 对话热度衰减（与对话池维护频率相关）
        3. 清理冷对话（基于热度）
        4. 强制执行大小限制
        """
        self._clean_expired_dialogues()  # 先清理过期对话
        self._decay_heat()               # 再进行热度衰减
        self._clean_cold_dialogues()     # 清理低热度对话
        self._enforce_size_limit()       # 最后控制池大小
    
    def add_dialogue(self, dialogue: ProcessingDialogue) -> None:
        """添加对话并更新计数器"""
        self.dialogues.append(dialogue)
        self.status_counter[dialogue.status.name.lower()] += 1
        self.maintain_pool()
    
    def update_dialogue_status(self, dialogue_index: int, new_status: ProcessingStatus) -> None:
        """更新对话状态并维护计数器"""
        for dialogue in self.dialogues:
            if dialogue.dialogue_index == dialogue_index:
                old_status = dialogue.status
                dialogue.status = new_status
                # 状态更新不增加热度，热度只与对话关联有关
                self.status_counter[old_status.name.lower()] -= 1
                self.status_counter[new_status.name.lower()] += 1
                break
    
    def analyze_dialogues(self) -> None:
        """分析对话关联性并附加上下文（占位实现）
        
        TODO: 
        1. 实现LLM分析逻辑
        2. 识别对话意图
        3. 识别对话关联
        4. 构建对话上下文
        """
        # 临时实现：为每个对话添加基础意图分析和上下文
        for dialogue in self.dialogues:
            # 1. 意图分析
            if not dialogue.intent_analysis:  # 如果还没有进行过意图分析
                # TODO: 这里将来需要调用LLM进行实际的意图分析
                dialogue.intent_analysis = IntentAnalysis(
                    intent="unknown",  # 临时占位
                    confidence=1.0,
                    parameters={
                        "text": dialogue.text,
                        "type": dialogue.type.name,
                        "is_narratage": dialogue.is_narratage,
                        "is_whisper": dialogue.is_whisper,
                        "tags": dialogue.tags
                    }
                )
            
            # 2. 上下文分析
            # TODO: 这里将来需要基于意图分析结果构建更丰富的上下文
            # 临时实现：模拟一些相关对话
            related_indices = []
            if dialogue.dialogue_index > 1:
                # 临时逻辑：假设与前一条对话相关
                related_indices = [dialogue.dialogue_index - 1]
                # 更新被引用对话的热度
                for related_index in related_indices:
                    related_dialogue = self.get_dialogue(related_index)
                    if related_dialogue:
                        related_dialogue.update_heat(0.3)  # 被引用时增加较多热度
            
            dialogue.context = DialogueContext(
                stage_index=None,
                related_dialogue_indices=related_indices,
                conversation_state={
                    "intent": dialogue.intent_analysis.intent,
                    "confidence": dialogue.intent_analysis.confidence,
                    "analyzed_at": datetime.now(timezone(timedelta(hours=8))).isoformat()
                }
            )
    
    def get_dialogue(self, dialogue_index: int) -> Optional[ProcessingDialogue]:
        """根据对话索引获取ProcessingDialogue"""
        for dialogue in self.dialogues:
            if dialogue.dialogue_index == dialogue_index:
                return dialogue
        return None
