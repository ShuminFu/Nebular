import heapq
import json
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from uuid import UUID

from pydantic import Field

from Opera.FastAPI.models import CamelBaseModel, StaffForUpdate
from Opera.core.api_response_parser import ApiResponseParser
from Opera.core.dialogue.enums import ProcessingStatus
from Opera.core.dialogue.models import ProcessingDialogue, DialogueContext, PersistentDialogueState
from Opera.core.dialogue.analyzers import DialogueAnalyzer
from ai_core.tools.opera_api.staff_api_tool import _SHARED_STAFF_TOOL


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

    def __init__(self, **data):
        """初始化对话池，创建对话分析器实例"""
        super().__init__(**data)
        self._analyzer = DialogueAnalyzer()

    @classmethod
    async def restore_from_api(cls, **kwargs) -> "DialoguePool":
        """从API恢复对话池状态的工厂方法

        TODO: 实现从API恢复数据的逻辑
        - 调用API获取持久化的PersistentDialogueState
        - 将PersistentDialogueState转换为ProcessingDialogue对象
        - 使用add_dialogue方法将ProcessingDialogue对象添加到对话池
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
        """分析对话关联性并附加上下文

        使用CrewAI实现的对话分析器来：
        1. 识别对话意图 summary:str
        2. 分析上下文关联 related_indices:List[int]
        3. 确保Opera隔离
        """
        # 按Opera分组处理对话
        opera_groups: Dict[UUID, List[ProcessingDialogue]] = {}
        for dialogue in self.dialogues:
            if not dialogue.opera_id in opera_groups:
                opera_groups[dialogue.opera_id] = []
            opera_groups[dialogue.opera_id].append(dialogue)

        # 对每个Opera的对话进行分析
        for opera_id, dialogues in opera_groups.items():
            # 创建临时对话池用于上下文分析
            temp_pool = DialoguePool()
            temp_pool.dialogues = dialogues

            for dialogue in dialogues:
                # 1. 意图分析
                if not dialogue.intent_analysis:
                    dialogue.intent_analysis = self._analyzer.analyze_intent(dialogue)

                # 2. 上下文分析
                related_indices = self._analyzer.analyze_context(dialogue, temp_pool)

                # 3. 更新对话上下文
                # 获取当前对话和相关对话中的最大stage_index
                current_stage_index = dialogue.context.stage_index if dialogue.context else None
                related_stage_indices = [
                    d.context.stage_index
                    for d in temp_pool.dialogues
                    if d.dialogue_index in related_indices
                    and d.context
                    and d.context.stage_index is not None
                ]

                # 如果有相关对话的stage_index，使用最大值；否则保持当前值
                max_stage_index = max(
                    [i for i in [current_stage_index] + related_stage_indices if i is not None],
                    default=current_stage_index
                )

                dialogue.context = DialogueContext(
                    stage_index=max_stage_index,
                    related_dialogue_indices=list(related_indices),
                    conversation_state={
                        "intent": dialogue.intent_analysis.intent,
                        "confidence": dialogue.intent_analysis.confidence,
                        "analyzed_at": datetime.now(timezone(timedelta(hours=8))).isoformat()
                    }
                )

                # 4. 更新相关对话的热度
                for related_index in related_indices:
                    related_dialogue = self.get_dialogue(related_index)
                    if related_dialogue and related_dialogue.opera_id == opera_id:
                        related_dialogue.update_heat(0.3)

                # TODO:可以根据上下文更新对话的类型(枚举值)，能够用于后续直接决定任务类型

    def get_dialogue(self, dialogue_index: int) -> Optional[ProcessingDialogue]:
        """根据对话索引获取ProcessingDialogue"""
        for dialogue in self.dialogues:
            if dialogue.dialogue_index == dialogue_index:
                return dialogue
        return None

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
                status_code, staff_data = ApiResponseParser.parse_response(
                    get_result)
                if status_code != 200 or not staff_data:
                    print(f"获取Staff {staff_id} 失败")
                    continue

                # 获取当前parameters
                try:
                    current_params = json.loads(
                        staff_data.get("parameter", "{}"))
                except json.JSONDecodeError:
                    current_params = {}

                # 获取该staff相关的对话
                staff_dialogues = [
                    dialogue for dialogue in self.dialogues
                    if staff_id in dialogue.receiver_staff_ids
                ]

                # 将对话转换为持久化状态
                dialogue_states = [
                    PersistentDialogueState.from_processing_dialogue(
                        dialogue).model_dump(by_alias=True)
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
                status_code, _ = ApiResponseParser.parse_response(
                    update_result)
                if status_code not in [200, 204]:
                    print(f"更新Staff {staff_id} 的parameters失败")

            except Exception as e:
                print(f"处理Staff {staff_id} 时发生错误: {str(e)}")
                continue
