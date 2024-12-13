"""Opera SignalR Bot对话处理器的实现。

负责将Staff的对话转换为任务并管理任务队列。
主要用于CrewManager和CrewRunner的对话处理和任务管理的桥接。
"""

from typing import List
from uuid import UUID

from Opera.Signalr.models.dialogue_queue import QueuedDialogue
from Opera.Signalr.models.task_queue import TaskQueueManager, TaskQueue


class BotDialogueProcessor:
    """Bot对话处理器
    
    负责:
    1. 接收来自多个Staff的对话
    2. 将对话转换为任务
    3. 管理任务队列
    """
    
    def __init__(self, bot_id: UUID):
        """初始化Bot对话处理器
        
        Args:
            bot_id: Bot的唯一标识
        """
        self.bot_id = bot_id
        self.task_queue_manager = TaskQueueManager(bot_id)
        
    def process_staff_dialogues(self, staff_queued_dialogues: List[QueuedDialogue]) -> None:
        """处理来自多个Staff的QueuedDialogue
        
        将对话按优先级和时间排序，然后依次添加到任务队列中。
        
        Args:
            staff_queued_dialogues: Staff的对话列表
        """
        # 按优先级和时间排序
        sorted_dialogues = sorted(
            staff_queued_dialogues,
            key=lambda x: (
                x.priority.value,  # 首要条件：优先级
                -x.metadata.source.created_at.timestamp()  # 次要条件：时间戳（负数使其降序）
            ),
            reverse=True
        )
        
        # 添加到任务队列
        for dialogue in sorted_dialogues:
            self.task_queue_manager.add_queued_dialogue(dialogue)
            
    def get_task_queue(self) -> TaskQueue:
        """获取当前任务队列
        
        Returns:
            当前的任务队列
        """
        return self.task_queue_manager.task_queue 

if __name__ == '__main__':
    # 使用示例
    from uuid import UUID
    
    # 创建Bot的对话处理器
    bot_processor = BotDialogueProcessor(bot_id=UUID("bot-uuid"))

    # 收集来自不同Staff的QueuedDialogue
    staff_dialogues = [
        QueuedDialogue(...),  # Staff 1的对话
        QueuedDialogue(...),  # Staff 2的对话
    ]

    # 处理所有Staff的对话
    bot_processor.process_staff_dialogues(staff_dialogues)

    # 获取整合后的任务队列
    task_queue = bot_processor.get_task_queue()