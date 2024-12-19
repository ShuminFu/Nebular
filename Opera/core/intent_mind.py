"""Opera SignalR Bot对话处理器的实现。

负责将Staff的对话转换为任务并管理任务队列。
主要用于CrewManager和CrewRunner的对话处理和任务管理的桥接。
"""

from typing import List, Dict, Set, Union
from uuid import UUID
from datetime import datetime, timezone, timedelta

from Opera.FastAPI.models import Dialogue
from Opera.core.dialogue_utils import (
    ProcessingDialogue, DialoguePool, DialoguePriority, DialogueType,
    ProcessingStatus, DialogueContext, IntentAnalysis
)
from Opera.core.task_queue import BotTask, BotTaskQueue, TaskType, TaskStatus
from Opera.signalr_client.opera_signalr_client import MessageReceivedArgs

class IntentMind:
    """Bot的意图处理器
    
    负责：
    1. 接收和管理Staff的对话
    2. 分析对话意图
    3. 转换为任务并进行调度
    """
    
    def __init__(self, task_queue: BotTaskQueue):
        self.dialogue_pool = DialoguePool()
        self.task_queue = task_queue  # 使用外部传入的任务队列
        self.staff_dialogues: Dict[UUID, Set[int]] = {}  # 记录每个Staff的对话索引
        
    def _determine_dialogue_priority(self, dialogue_obj: Union[Dialogue, MessageReceivedArgs]) -> DialoguePriority:
        """确定对话的优先级
        
        基于对话的属性（如标签、提及的Staff等）确定优先级
        """
        if dialogue_obj.tags and "urgent" in dialogue_obj.tags.lower():
            return DialoguePriority.URGENT
        if dialogue_obj.mentioned_staff_ids:
            return DialoguePriority.HIGH
        return DialoguePriority.NORMAL
        
    def _determine_dialogue_type(self, dialogue_obj: Union[Dialogue, MessageReceivedArgs]) -> DialogueType:
        """确定对话的类型
        
        基于对话的属性确定类型：
        1. 系统消息（通过tags判断）
        2. 旁白（is_narratage）
        3. 私密对话（is_whisper）- 私密对话同时也是提及对话
        4. 提及对话（mentioned_staff_ids非空）
        5. 普通对话（其他情况）
        
        注意：
        - whisper类型的对话自动被视为mention类型
        - mention类型的对话不一定是whisper类型
        
        Args:
            dialogue_obj: 对话对象，可以是Dialogue或MessageReceivedArgs
            
        Returns:
            DialogueType: 对话类型枚举值
        """
        # 首先检查是否是系统消息
        if dialogue_obj.tags and "system" in dialogue_obj.tags.lower():
            return DialogueType.SYSTEM
            
        # 检查是否是旁白
        if dialogue_obj.is_narratage:
            return DialogueType.NARRATAGE
            
        # 检查是否是私密对话
        if dialogue_obj.is_whisper:
            return DialogueType.WHISPER
            
        # 检查是否有提及其他Staff
        if dialogue_obj.mentioned_staff_ids and len(dialogue_obj.mentioned_staff_ids) > 0:
            return DialogueType.MENTION
            
        # 默认为普通对话
        return DialogueType.NORMAL
        
    def _create_task_from_dialogue(self, dialogue: ProcessingDialogue) -> BotTask:
        """从对话创建任务
        
        基于对话类型进行初步的任务类型判断，后续会通过意图分析来更新更具体的任务类型。
        创建任务后会将对话状态更新为已完成。
        
        Args:
            dialogue: 处理中的对话对象
            
        Returns:
            BotTask: 创建的任务对象
        """
        # 基于对话类型进行初步的任务类型判断
        task_type = TaskType.CONVERSATION  # 默认为基础对话处理
        
        if dialogue.type == DialogueType.SYSTEM:
            task_type = TaskType.SYSTEM  # 系统消息
        elif dialogue.type in [DialogueType.WHISPER, DialogueType.MENTION]:
            task_type = TaskType.CHAT_RESPONSE  # 需要响应的对话
        elif dialogue.type == DialogueType.NARRATAGE:
            task_type = TaskType.ANALYSIS  # 旁白需要分析
            
        # 创建任务
        task = BotTask(
            priority=dialogue.priority,
            type=task_type,
            description=f"Process dialogue {dialogue.dialogue_index} from staff {dialogue.staff_id}",
            parameters={
                "text": dialogue.text,
                "tags": dialogue.tags,
                "mentioned_staff_ids": [str(id) for id in (dialogue.mentioned_staff_ids or [])],
                "dialogue_type": dialogue.type.name,
                "intent": dialogue.intent_analysis.model_dump() if dialogue.intent_analysis else None,
                "context": dialogue.context.model_dump()
            },
            source_dialogue_index=dialogue.dialogue_index,
            source_staff_id=dialogue.staff_id
        )
        
        # 更新对话状态为已完成
        self.dialogue_pool.update_dialogue_status(dialogue.dialogue_index, ProcessingStatus.COMPLETED)
        
        return task
        
    async def _process_single_dialogue(self, dialogue_obj: Union[Dialogue, MessageReceivedArgs],
                               is_message: bool = True) -> None:
        """处理单个对话的通用方法
        
        Args:
            dialogue_obj: 对话对象，可以是Dialogue或MessageReceivedArgs
            is_message: 是否是MessageReceivedArgs类型
        """
        # 确定优先级和类型
        priority = self._determine_dialogue_priority(dialogue_obj)
        dialogue_type = self._determine_dialogue_type(dialogue_obj)
        
        # 创建ProcessingDialogue
        processing_dialogue = (
            ProcessingDialogue.from_message_args(dialogue_obj, priority=priority, dialogue_type=dialogue_type)
            if is_message
            else ProcessingDialogue.from_dialogue(dialogue_obj, priority=priority, dialogue_type=dialogue_type)
        )
        
        # 添加到对话池
        await self.dialogue_pool.add_dialogue(processing_dialogue)
        
        # 记录Staff的对话
        staff_id = dialogue_obj.sender_staff_id if is_message else dialogue_obj.staff_id
        if staff_id:
            if staff_id not in self.staff_dialogues:
                self.staff_dialogues[staff_id] = set()
            self.staff_dialogues[staff_id].add(dialogue_obj.index)
            
        return processing_dialogue.dialogue_index

    async def process_message(self, message: MessageReceivedArgs) -> None:
        """处理单个MessageReceivedArgs消息"""
        dialogue_index = await self._process_single_dialogue(message, is_message=True)
        
        # 分析对话
        self.dialogue_pool.analyze_dialogues()
        
        # 从对话池中获取已分析的对话来创建任务
        analyzed_dialogue = self.dialogue_pool.get_dialogue(dialogue_index)
        if analyzed_dialogue and analyzed_dialogue.status == ProcessingStatus.PENDING:
            task = self._create_task_from_dialogue(analyzed_dialogue)
            self.task_queue.add_task(task)

    def process_dialogues(self, dialogues: List[Dialogue]) -> None:
        """处理对话列表"""
        # 按时间排序
        sorted_dialogues = sorted(dialogues, key=lambda x: x.time)
        
        # 处理每个对话
        dialogue_indices = []
        for dialogue in sorted_dialogues:
            dialogue_index = self._process_single_dialogue(dialogue, is_message=False)
            dialogue_indices.append(dialogue_index)
        
        # 对话池分析
        self.dialogue_pool.analyze_dialogues()
        
        # 创建任务
        for dialogue_index in dialogue_indices:
            analyzed_dialogue = self.dialogue_pool.get_dialogue(dialogue_index)
            if analyzed_dialogue and analyzed_dialogue.status == ProcessingStatus.PENDING:
                task = self._create_task_from_dialogue(analyzed_dialogue)
                self.task_queue.add_task(task)

    def get_staff_dialogues(self, staff_id: UUID) -> Set[int]:
        """获取对话发送人为指定Staff的所有对话索引"""
        return self.staff_dialogues.get(staff_id, set())

    def get_dialogue_pool(self) -> DialoguePool:
        """获取当前对话池"""
        return self.dialogue_pool

if __name__ == '__main__':
    from Opera.core.tests.test_intent_mind import main
    main()