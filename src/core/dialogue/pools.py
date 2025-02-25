import heapq
import json
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any
from uuid import UUID
import asyncio

from pydantic import Field

from src.opera_service.api.models import CamelBaseModel, StaffForUpdate
from src.core.parser.api_response_parser import ApiResponseParser
from src.core.dialogue.enums import ProcessingStatus
from src.core.dialogue.models import ProcessingDialogue, PersistentDialogueState
from src.crewai_ext.tools.opera_api.staff_api_tool import _SHARED_STAFF_TOOL

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
    max_size: int = Field(default=100, description="对话池最大容量")
    min_heat_threshold: float = Field(default=0.5, description="最小热度阈值")
    heat_decay_rate: float = Field(default=0.1, description="每次维护时的热度衰减率")
    max_age_hours: int = Field(default=24, description="对话最大保留时间（小时）")

    # Opera分析状态
    opera_analysis_state: Dict[UUID, Dict[str, Any]] = Field(default_factory=dict, description="记录每个Opera的分析状态", exclude=True)

    def __init__(self, **data):
        """初始化对话池，创建对话分析器实例"""
        super().__init__(**data)

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
        self._decay_heat()  # 再进行热度衰减
        self._clean_cold_dialogues()  # 清理低热度对话
        self._enforce_size_limit()  # 最后控制池大小
        # 维护完成后持久化
        # await self._persist_to_api()

    async def add_dialogue(self, dialogue: ProcessingDialogue) -> None:
        """添加对话并更新计数器"""
        self.dialogues.append(dialogue)
        self.status_counter[dialogue.status.name.lower()] += 1

        # 标记Opera需要重新分析
        if dialogue.opera_id not in self.opera_analysis_state:
            self.opera_analysis_state[dialogue.opera_id] = {"last_analyzed_at": None, "needs_analysis": True}
        else:
            self.opera_analysis_state[dialogue.opera_id]["needs_analysis"] = True

        await self.maintain_pool()

    async def update_dialogue_status(self, dialogue_index: int, new_status: ProcessingStatus) -> None:
        """更新对话状态并维护计数器"""
        for dialogue in self.dialogues:
            if dialogue.dialogue_index == dialogue_index:
                old_status = dialogue.status
                dialogue.status = new_status
                # 状态更新不增加热度，热度只与对话关联有关
                old_status_name = old_status.name.lower()
                new_status_name = new_status.name.lower()

                # 确保状态计数器中有这些状态
                if old_status_name not in self.status_counter:
                    self.status_counter[old_status_name] = 0
                if new_status_name not in self.status_counter:
                    self.status_counter[new_status_name] = 0

                # 更新计数
                self.status_counter[old_status_name] = max(0, self.status_counter[old_status_name] - 1)
                self.status_counter[new_status_name] += 1

                # 状态更新后持久化
                # await self._persist_to_api()
                break

    async def analyze_dialogues(self, target_opera_id: Optional[UUID] = None) -> None:
        """分析对话关联性并附加上下文

        使用CrewAI实现的对话分析器来：
        1. 识别对话意图
        2. 分析上下文关联
        3. 确保Opera隔离

        Args:
            target_opera_id: 可选的目标Opera ID。如果指定，只分析该Opera的对话。
        """
        now = datetime.now(timezone(timedelta(hours=8)))
        from src.crewai_ext.flows.analysis_flow import AnalysisFlow

        # 按Opera分组处理对话
        opera_groups: Dict[UUID, List[ProcessingDialogue]] = {}
        for dialogue in self.dialogues:
            if dialogue.opera_id not in opera_groups:
                opera_groups[dialogue.opera_id] = []
            opera_groups[dialogue.opera_id].append(dialogue)

        # 确定需要分析的Opera
        operas_to_analyze = set()
        for opera_id in opera_groups:
            # 如果指定了目标Opera，只分析该Opera
            if target_opera_id and opera_id != target_opera_id:
                continue

            # 检查是否需要重新分析
            state = self.opera_analysis_state.get(opera_id, {"last_analyzed_at": None, "needs_analysis": True})

            if state["needs_analysis"]:
                operas_to_analyze.add(opera_id)

        # 对需要分析的Opera进行处理
        analysis_tasks = []
        for opera_id in operas_to_analyze:
            dialogues = opera_groups[opera_id]

            # 创建临时对话池用于上下文分析
            temp_pool = DialoguePool()
            temp_pool.dialogues = dialogues

            for dialogue in dialogues:
                # 使用AnalysisFlow进行分析
                if not dialogue.intent_analysis:
                    flow = AnalysisFlow(dialogue=dialogue, temp_pool=temp_pool)
                    # 创建异步任务并保存相关对话引用
                    task = asyncio.create_task(
                        self._process_dialogue_analysis(flow, dialogue.opera_id),
                        name=f"analysis_{opera_id}_{dialogue.dialogue_index}",
                    )
                    analysis_tasks.append(task)

        # 等待所有分析任务完成
        if analysis_tasks:
            await asyncio.gather(*analysis_tasks)

        # 更新分析状态
        self.opera_analysis_state[target_opera_id] = {"last_analyzed_at": now, "needs_analysis": False}

    async def _process_dialogue_analysis(self, flow, opera_id: UUID) -> None:
        """处理单个对话分析任务"""

        try:
            result = await flow.kickoff_async()
            related_indices = flow.state.related_indices

            # 更新相关对话热度（在原始对话池中操作）
            for related_index in related_indices:
                related_dialogue = self.get_dialogue(related_index)
                if related_dialogue and related_dialogue.opera_id == opera_id:
                    related_dialogue.update_heat(0.3)

        except Exception as e:
            print(f"分析对话 {flow.dialogue.dialogue_index} 时出错: {str(e)}")

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

        # 保留未过期的对话，并标记被清理的Opera需要重新分析
        old_dialogues = {d.opera_id: d for d in self.dialogues}
        self.dialogues = [
            d for d in self.dialogues
            if (now - d.created_at) <= max_age
        ]

        # 如果有对话被清理，标记相应Opera需要重新分析
        current_dialogues = {d.opera_id: d for d in self.dialogues}
        for opera_id in old_dialogues:
            if opera_id not in current_dialogues:
                if opera_id in self.opera_analysis_state:
                    self.opera_analysis_state[opera_id]["needs_analysis"] = True

        # 更新状态计数器
        if len(old_dialogues) != len(self.dialogues):
            self.status_counter = Counter(
                d.status.name.lower() for d in self.dialogues)

    def _clean_cold_dialogues(self) -> None:
        """清理冷对话（热度低于阈值）"""
        old_dialogues = {d.opera_id: d for d in self.dialogues}
        self.dialogues = [
            d for d in self.dialogues
            if d.heat >= self.min_heat_threshold
        ]

        # 如果有对话被清理，标记相应Opera需要重新分析
        current_dialogues = {d.opera_id: d for d in self.dialogues}
        for opera_id in old_dialogues:
            if opera_id not in current_dialogues:
                if opera_id in self.opera_analysis_state:
                    self.opera_analysis_state[opera_id]["needs_analysis"] = True

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
