"""Opera SignalR 对话队列的数据模型定义。"""

from pydantic import Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from uuid import UUID
from enum import IntEnum
from collections import Counter
import heapq
import json

from Opera.signalr_client.opera_signalr_client import MessageReceivedArgs
from Opera.FastAPI.models import CamelBaseModel, StaffForUpdate
from ai_core.tools.opera_api.dialogue_api_tool import _SHARED_DIALOGUE_TOOL
from ai_core.tools.opera_api.staff_api_tool import _SHARED_STAFF_TOOL
from Opera.core.api_response_parser import ApiResponseParser


class DialoguePriority(IntEnum):
    """对话优先级枚举"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


class DialogueType(IntEnum):
    """对话类型枚举 - 基于对话的基础特征进行分类"""
    NORMAL = 1      # 普通对话
    WHISPER = 2     # 私密对话（悄悄话）
    MENTION = 3     # 提及对话（@某人）
    NARRATAGE = 4   # 旁白
    SYSTEM = 5      # 系统消息


class ProcessingStatus(IntEnum):
    """处理状态枚举"""
    PENDING = 1
    PROCESSING = 2
    COMPLETED = 3
    FAILED = 4


class DialogueContext(CamelBaseModel):
    """对话上下文模型"""
    stage_index: Optional[int] = Field(default=None, description="对话阶段索引")
    related_dialogue_indices: List[int] = Field(
        default_factory=list, description="相关对话索引列表")
    conversation_state: Dict[str, Any] = Field(
        default_factory=dict, description="对话状态信息")


class IntentAnalysis(CamelBaseModel):
    """意图分析结果模型"""
    intent: str = Field(..., description="识别出的意图")
    confidence: float = Field(..., description="置信度")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="提取的参数")


class ProcessingDialogue(CamelBaseModel):
    """处理中的对话模型

    基于SignalR客户端中接收到的的MessageReceivedArgs，添加了处理相关的属性和状态。
    用于跟踪和管理对话的处理过程。
    """
    # 基础对话信息
    dialogue_index: int = Field(..., description="对话索引")
    created_at: datetime = Field(default_factory=lambda: datetime.now(
        timezone(timedelta(hours=8))), description="创建时间 (UTC+8)")
    sender_staff_id: Optional[UUID] = Field(default=None, description="发送者Staff ID")
    receiver_staff_ids: List[UUID] = Field(default_factory=list, description="接收者Staff ID列表")
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
    receiver_staff_ids: List[UUID] = Field(default_factory=list, description="接收者Staff ID列表")

    # 意图识别处理结果（必需）
    priority: DialoguePriority = Field(..., description="处理优先级")
    type: DialogueType = Field(..., description="对话类型")
    intent_analysis: Optional[IntentAnalysis] = Field(default=None, description="意图分析结果")
    context: DialogueContext = Field(default_factory=DialogueContext, description="对话上下文")

    # 对话池状态信息（必需）
    status: ProcessingStatus = Field(default=ProcessingStatus.PENDING, description="处理状态")
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

    def update_processing_dialogue(self, dialogue: ProcessingDialogue) -> None:
        """使用持久化状态更新ProcessingDialogue对象"""
        dialogue.priority = self.priority
        dialogue.type = self.type
        dialogue.intent_analysis = self.intent_analysis
        dialogue.context = self.context
        dialogue.status = self.status
        dialogue.heat = self.heat
        dialogue.reference_count = self.reference_count


class DialoguePool(CamelBaseModel):
    """对话池模型

    管理和追踪所有处理中的对话。
    提供对话状态管理和统计功能。
    """
    dialogues: List[ProcessingDialogue] = Field(
        default_factory=list, description="处理中的对话列表")
    status_counter: Dict[str, int] = Field(
        default_factory=lambda: {
            status.name.lower(): 0 for status in ProcessingStatus},
        description="状态计数器"
    )

    # 配置参数
    max_size: int = Field(default=1000, description="对话池最大容量")
    min_heat_threshold: float = Field(default=0.5, description="最小热度阈值")
    heat_decay_rate: float = Field(default=0.1, description="每次维护时的热度衰减率")
    max_age_hours: int = Field(default=24, description="对话最大保留时间（小时）")

    async def _persist_to_api(self) -> None:
        """将对话池状态持久化到API

        将对话池中的每个对话以PersistentDialogueState的形式持久化到每个receiver staff的parameters中。
        步骤：
        1. 获取所有需要更新的staff
        2. 获取每个staff当前的parameters
        3. 更新parameters中的对话状态
        4. 将更新后的parameters保存回API
        """
        # 创建StaffTool实例
        staff_tool = _SHARED_STAFF_TOOL

        # 收集所有需要更新的staff_id
        staff_ids = set()
        for dialogue in self.dialogues:
            staff_ids.update(dialogue.receiver_staff_ids)

        # 对每个staff进行更新
        for staff_id in staff_ids:
            try:
                # 获取当前staff的信息
                get_result = staff_tool.run(
                    action="get",
                    opera_id=self.dialogues[0].opera_id if self.dialogues else None,
                    staff_id=staff_id
                )

                # 解析API响应
                status_code, staff_data = ApiResponseParser.parse_response(get_result)
                if status_code != 200 or not staff_data:
                    print(f"获取Staff {staff_id} 失败")
                    continue

                # 获取当前parameters
                try:
                    current_params = json.loads(staff_data.get("parameter", "{}"))
                except json.JSONDecodeError:
                    current_params = {}

                # 获取该staff相关的对话
                staff_dialogues = [
                    dialogue for dialogue in self.dialogues
                    if staff_id in dialogue.receiver_staff_ids
                ]

                # 将对话转换为持久化状态
                dialogue_states = [
                    PersistentDialogueState.from_processing_dialogue(dialogue).model_dump(by_alias=True)
                    for dialogue in staff_dialogues
                ]

                # 更新parameters
                current_params["dialogueStates"] = dialogue_states

                # 更新staff的parameters
                update_result = staff_tool.run(
                    action="update",
                    opera_id=self.dialogues[0].opera_id if self.dialogues else None,
                    staff_id=staff_id,
                    data=StaffForUpdate(parameter=json.dumps(current_params))
                )

                # 检查更新结果
                status_code, _ = ApiResponseParser.parse_response(update_result)
                if status_code not in [200, 204]:
                    print(f"更新Staff {staff_id} 的parameters失败")

            except Exception as e:
                print(f"处理Staff {staff_id} 时发生错误: {str(e)}")
                continue

    @classmethod
    def create(cls, **kwargs) -> "DialoguePool":
        """创建对话池的工厂方法

        Args:
            **kwargs: 配置参数

        Returns:
            DialoguePool: 新创建的对话池实例
        """
        return cls(**kwargs)

    @classmethod
    async def restore_from_api(cls, **kwargs) -> "DialoguePool":
        """从API恢复对话池状态的工厂方法

        TODO: 实现从API恢复数据的逻辑
        - 调用API获取持久化的对话数据
        - 将API数据转换为ProcessingDialogue对象
        - 重建对话池的状态计数器
        - 处理可能的API调用失败情况
        - 考虑是否需要增量恢复机制

        Args:
            **kwargs: 配置参数，可能包括时间范围、过滤条件等

        Returns:
            DialoguePool: 恢复的对话池实例
        """
        # 创建一个新的对话池实例
        pool = cls(**kwargs)

        # 从API获取持久化的对话数据
        # restored_data = await dialogue_api.get_persisted_dialogues(**kwargs)

        # 将API数据转换为ProcessingDialogue对象
        # pool.dialogues = [ProcessingDialogue(**data) for data in restored_data]

        # 重建状态计数器
        # pool.status_counter = Counter(d.status.name.lower() for d in pool.dialogues)

        return pool

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
            self.status_counter = Counter(
                d.status.name.lower() for d in self.dialogues)

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

    async def maintain_pool(self) -> None:
        """维护对话池

        1. 清理过期对话（基于时间）
        2. 对话热度衰减（与对话池维护频率相关）
        3. 清理冷对话（基于热度）
        4. 强制执行大小限制
        5. 持久化更新后的状态
        """
        self._clean_expired_dialogues()  # 先清理过期对话
        self._decay_heat()         # 再进行热度衰减
        self._clean_cold_dialogues()     # 清理低热度对话
        self._enforce_size_limit()       # 最后控制池大小
        # 维护完成后持久化
        await self._persist_to_api()

    async def add_dialogue(self, dialogue: ProcessingDialogue) -> None:
        """添加对话并更新计数器"""
        self.dialogues.append(dialogue)
        self.status_counter[dialogue.status.name.lower()] += 1
        await self.maintain_pool()
        # 添加对话后持久化
        await self._persist_to_api()

    async def update_dialogue_status(self, dialogue_index: int, new_status: ProcessingStatus) -> None:
        """更新对话状态并维护计数器"""
        for dialogue in self.dialogues:
            if dialogue.dialogue_index == dialogue_index:
                old_status = dialogue.status
                dialogue.status = new_status
                # 状态更新不增加热度，热度只与对话关联有关
                self.status_counter[old_status.name.lower()] -= 1
                self.status_counter[new_status.name.lower()] += 1
                # 状态更新后持久化
                await self._persist_to_api()
                break

    def analyze_dialogues(self) -> None:
        """分析对话关联性并附加上下文（占位实现）

        TODO: analyze_dialogues 
        1. 实现LLM分析逻辑
        2. 识别对话意图
        3. 识别对话关联
        4. 构建对话上下文
        5.  需要注意的是Bot可能是跨opera的，不应该让staff看到另一个opera的信息作为context。

        """
        # 临时实现：为每个对话添加基础意图分析和上下文
        for dialogue in self.dialogues:
            # 1. 意图分析
            if not dialogue.intent_analysis:  # 如果还没有进行过意图分析
                # 这里将来需要调用LLM进行实际的意图分析
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

    async def restore_dialogue(self, persistent_state: PersistentDialogueState) -> None:
        """从持久化状态恢复单个对话
        
        Args:
            persistent_state: 持久化的对话状态
        """
        # 从API获取对话基础信息
        result = await _SHARED_DIALOGUE_TOOL.run(
            action="get",
            opera_id=self.opera_id,
            dialogue_index=persistent_state.dialogue_index
        )

        # 解析API响应
        status_code, dialogue_data = ApiResponseParser.parse_response(result)
        if status_code != 200 or not dialogue_data:
            raise ValueError(f"Failed to restore dialogue {persistent_state.dialogue_index}")

        # 将Dialogue数据转换为MessageReceivedArgs
        message_args = MessageReceivedArgs(
            index=dialogue_data["index"],
            time=dialogue_data["time"],
            stage_index=dialogue_data.get("stage_index"),
            sender_staff_id=dialogue_data.get("staff_id"),
            is_narratage=dialogue_data["is_narratage"],
            is_whisper=dialogue_data["is_whisper"],
            text=dialogue_data["text"],
            tags=dialogue_data.get("tags"),
            mentioned_staff_ids=dialogue_data.get("mentioned_staff_ids", []),
            opera_id=self.opera_id,  # 从对话池获取
            receiver_staff_ids=[]     # 这个信息可能需要从其他地方获取
        )

        # 创建新的对话对象
        dialogue = ProcessingDialogue.from_message_args(
            message_args,
            priority=persistent_state.priority,
            dialogue_type=persistent_state.type
        )

        # 使用持久化状态更新对话
        persistent_state.update_processing_dialogue(dialogue)

        # 添加到对话池
        await self.add_dialogue(dialogue)
