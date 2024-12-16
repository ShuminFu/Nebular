"""Opera SignalR Bot对话处理器的实现。

负责将Staff的对话转换为任务并管理任务队列。
主要用于CrewManager和CrewRunner的对话处理和任务管理的桥接。
"""

from typing import List, Dict, Set
from uuid import UUID
from datetime import datetime, timezone, timedelta

from Opera.FastAPI.models import Dialogue
from Opera.core.dialogue_utils import (
    ProcessingDialogue, DialoguePool, DialoguePriority, DialogueType,
    ProcessingStatus, DialogueContext, IntentAnalysis
)
from Opera.core.task_queue import BotTask, BotTaskQueue, TaskType, TaskStatus


class IntentMind:
    """Bot的意图处理器
    
    负责：
    1. 接收和管理Staff的对话
    2. 分析对话意图
    3. 转换为任务并进行调度
    """
    
    def __init__(self, bot_id: UUID):
        self.bot_id = bot_id
        self.dialogue_pool = DialoguePool()
        self.task_queue = BotTaskQueue()
        self.staff_dialogues: Dict[UUID, Set[int]] = {}  # 记录每个Staff的对话索引
        
    def _determine_dialogue_priority(self, dialogue: Dialogue) -> DialoguePriority:
        """确定对话的优先级
        
        基于对话的属性（如标签、提及的Staff等）确定优先级
        """
        if dialogue.tags and "urgent" in dialogue.tags.lower():
            return DialoguePriority.URGENT
        if dialogue.mentioned_staff_ids:
            return DialoguePriority.HIGH
        return DialoguePriority.NORMAL
        
    def _determine_dialogue_type(self, dialogue: Dialogue) -> DialogueType:
        """确定对话的类型
        
        基于对话的内容和标签确定类型
        """
        if dialogue.tags:
            if "command" in dialogue.tags.lower():
                return DialogueType.COMMAND
            if "query" in dialogue.tags.lower():
                return DialogueType.QUERY
        return DialogueType.TEXT
        
    def _create_task_from_dialogue(self, dialogue: ProcessingDialogue) -> BotTask:
        """从对话创建任务"""
        task_type = TaskType.CONVERSATION
        if dialogue.type == DialogueType.COMMAND:
            task_type = TaskType.ACTION
        elif dialogue.type == DialogueType.QUERY:
            task_type = TaskType.ANALYSIS
            
        return BotTask(
            id=UUID(),
            priority=dialogue.priority,
            type=task_type,
            description=f"Process dialogue {dialogue.dialogue_index} from staff {dialogue.staff_id}",
            parameters={
                "text": dialogue.text,
                "tags": dialogue.tags,
                "mentioned_staff_ids": [str(id) for id in dialogue.mentioned_staff_ids],
                "intent": dialogue.intent_analysis.model_dump() if dialogue.intent_analysis else None,
                "context": dialogue.context.model_dump()
            },
            source_dialogue_index=dialogue.dialogue_index,
            source_staff_id=dialogue.staff_id
        )
        
    def process_dialogues(self, dialogues: List[Dialogue]) -> None:
        """处理对话列表
        
        1. 转换为ProcessingDialogue并添加到对话池
        2. 使用对话池进行上下文分析（占位，后续实现LLM分析）
        3. 基于带上下文的ProcessingDialogue创建任务
        """
        # 按时间排序
        sorted_dialogues = sorted(dialogues, key=lambda x: x.time)
        
        # 1. 转换对话并添加到对话池
        processing_dialogues = []  # 保存转换后的对话，避免重复获取
        for dialogue in sorted_dialogues:
            # 创建ProcessingDialogue
            priority = self._determine_dialogue_priority(dialogue)
            dialogue_type = self._determine_dialogue_type(dialogue)
            processing_dialogue = ProcessingDialogue.from_dialogue(
                dialogue, 
                priority=priority,
                dialogue_type=dialogue_type
            )
            
            # 添加到对话池和临时列表
            self.dialogue_pool.add_dialogue(processing_dialogue)
            processing_dialogues.append(processing_dialogue)
            
            # 记录Staff的对话
            if dialogue.staff_id:
                if dialogue.staff_id not in self.staff_dialogues:
                    self.staff_dialogues[dialogue.staff_id] = set()
                self.staff_dialogues[dialogue.staff_id].add(dialogue.index)
        
        # 2. 对话池分析 - 使用占位符
        self.dialogue_pool.analyze_dialogues()
        
        # 3. 直接使用已经增强的processing_dialogues创建任务
        for processing_dialogue in processing_dialogues:
            task = self._create_task_from_dialogue(processing_dialogue)
            self.task_queue.add_task(task)
        
    def get_staff_dialogues(self, staff_id: UUID) -> Set[int]:
        """获取对话发送人为指定Staff的所有对话索引"""
        return self.staff_dialogues.get(staff_id, set())
    
    def get_task_queue(self) -> BotTaskQueue:
        """获取当前任务队列"""
        return self.task_queue
    
    def get_dialogue_pool(self) -> DialoguePool:
        """获取当前对话池"""
        return self.dialogue_pool

if __name__ == '__main__':
    # 使用示例
    from uuid import UUID
    
    # 创建Bot的对话处理器
    bot_processor = IntentMind(bot_id=UUID("bot-uuid"))

    # 收集来自不同Staff的ProcessingDialogue
    staff_dialogues = [
        ProcessingDialogue(...),  # Staff 1的对话
        ProcessingDialogue(...),  # Staff 2的对话
    ]

    # 处理所有Staff的对话
    bot_processor.process_staff_dialogues(staff_dialogues)