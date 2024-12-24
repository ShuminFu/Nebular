"""Opera SignalR Bot对话处理器的实现。

负责将Staff的对话转换为任务并管理任务队列。
主要用于CrewManager和CrewRunner的对话处理和任务管理的桥接。
"""

from typing import Set, Dict
from uuid import UUID
import json

from Opera.core.dialogue_utils import (
    ProcessingDialogue, DialoguePool, DialoguePriority, DialogueType,
    ProcessingStatus
)
from Opera.core.task_utils import BotTask, BotTaskQueue, TaskType, TaskPriority
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

    def _determine_dialogue_priority(self, message: MessageReceivedArgs) -> DialoguePriority:
        """确定对话的优先级

        基于对话的属性（如标签、提及的Staff等）确定优先级
        """
        if message.tags:
            # 检查是否是任务回调，任务回调应该是紧急优先级
            if "task_callback" in message.tags.lower():
                return DialoguePriority.URGENT
            if "urgent" in message.tags.lower():
                return DialoguePriority.URGENT
        if message.mentioned_staff_ids:
            return DialoguePriority.HIGH
        return DialoguePriority.NORMAL

    def _determine_dialogue_type(self, message: MessageReceivedArgs) -> DialogueType:
        """确定对话的类型

        基于对话的属性确定类型：
        1. 系统消息（通过tags判断）
        2. 任务回调（通过tags判断）
        3. 旁白（is_narratage）
        4. 私密对话（is_whisper）- 私密对话同时也是提及对话
        5. 提及对话（mentioned_staff_ids非空）
        6. 普通对话（其他情况）
        注意：
        - whisper类型的对话自动被视为mention类型
        - mention类型的对话不一定是whisper类型

        Args:
            message: MessageReceivedArgs对象

        Returns:
            DialogueType: 对话类型枚举值
        """
        # 首先检查是否是系统消息或任务回调
        if message.tags:
            if "system" in message.tags.lower():
                return DialogueType.SYSTEM
            if "task_callback" in message.tags.lower():
                return DialogueType.SYSTEM  # 任务回调也作为系统消息处理

        # 检查是否是旁白
        if message.is_narratage:
            return DialogueType.NARRATAGE

        # 检查是否是私密对话
        if message.is_whisper:
            return DialogueType.WHISPER

        # 检查是否有提及其他Staff
        if message.mentioned_staff_ids and len(message.mentioned_staff_ids) > 0:
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
        self.dialogue_pool.update_dialogue_status(dialogue.dialogue_index, ProcessingStatus.PROCESSING)

        # 基于对话类型进行初步的任务类型判断
        task_type = TaskType.CONVERSATION  # 默认为基础对话处理
        task_priority = dialogue.priority
        task_parameters = {
            "text": dialogue.text,
            "tags": dialogue.tags,
            "mentioned_staff_ids": [str(id) for id in (dialogue.mentioned_staff_ids or [])],
            "dialogue_type": dialogue.type.name,
            "intent": dialogue.intent_analysis.model_dump() if dialogue.intent_analysis else None,
            "context": dialogue.context.model_dump() if dialogue.context else None,
            "opera_id": str(dialogue.opera_id) if dialogue.opera_id else None
        }

        # 检查是否是任务回调
        if dialogue.tags and "task_callback" in dialogue.tags.lower():
            task_type = TaskType.CALLBACK
            task_priority = TaskPriority.URGENT
            # 尝试从对话文本中解析任务回调信息
            try:
                callback_data = json.loads(dialogue.text)
                # 更新任务参数
                task_parameters.update(callback_data.get("parameters", {}))
                # 如果callback_data中指定了任务类型，使用它
                if "type" in callback_data:
                    try:
                        task_type = TaskType[callback_data["type"]]
                    except (KeyError, ValueError):
                        pass  # 如果无法解析任务类型，保持默认的CALLBACK类型
            except json.JSONDecodeError:
                pass

        elif dialogue.type == DialogueType.SYSTEM:
            task_type = TaskType.SYSTEM
        elif dialogue.type in [DialogueType.WHISPER, DialogueType.MENTION]:
            task_type = TaskType.CHAT_RESPONSE
        elif dialogue.type == DialogueType.NARRATAGE:
            task_type = TaskType.ANALYSIS

        # 创建任务
        task = BotTask(
            priority=task_priority,
            type=task_type,
            description=f"Process dialogue {dialogue.dialogue_index} from staff {dialogue.sender_staff_id}",
            parameters=task_parameters,
            source_dialogue_index=dialogue.dialogue_index,
            response_staff_id=dialogue.receiver_staff_ids[0] if dialogue.receiver_staff_ids else None,
            source_staff_id=dialogue.sender_staff_id  # 设置源Staff ID为对话的发送者
        )

        # 更新对话状态为已完成
        self.dialogue_pool.update_dialogue_status(dialogue.dialogue_index, ProcessingStatus.COMPLETED)

        return task

    async def _process_single_message(self, message: MessageReceivedArgs) -> int:
        """处理单个对话

        Args:
            message: MessageReceivedArgs对象

        Returns:
            int: 对话索引
        """
        # 确定优先级和类型
        priority = self._determine_dialogue_priority(message)
        dialogue_type = self._determine_dialogue_type(message)

        # 创建ProcessingDialogue
        processing_dialogue = ProcessingDialogue.from_message_args(
            message, priority=priority, dialogue_type=dialogue_type
        )

        # 添加到对话池
        await self.dialogue_pool.add_dialogue(processing_dialogue)

        # 记录Staff的对话
        if message.sender_staff_id:
            if message.sender_staff_id not in self.staff_dialogues:
                self.staff_dialogues[message.sender_staff_id] = set()
            self.staff_dialogues[message.sender_staff_id].add(message.index)

        return processing_dialogue.dialogue_index

    async def process_message(self, message: MessageReceivedArgs) -> None:
        """处理单个MessageReceivedArgs消息"""
        dialogue_index = await self._process_single_message(message)

        # 分析对话
        self.dialogue_pool.analyze_dialogues()

        # 从对话池中获取已分析的对话来创建任务
        analyzed_dialogue = self.dialogue_pool.get_dialogue(dialogue_index)
        if analyzed_dialogue and analyzed_dialogue.status == ProcessingStatus.PENDING:
            task = self._create_task_from_dialogue(analyzed_dialogue)
            await self.task_queue.add_task(task)

    def get_staff_dialogues(self, staff_id: UUID) -> Set[int]:
        """获取对话发送人为指定Staff的所有对话索引"""
        return self.staff_dialogues.get(staff_id, set())

    def get_dialogue_pool(self) -> DialoguePool:
        """获取当前对话池"""
        return self.dialogue_pool


if __name__ == '__main__':
    from Opera.core.tests.test_intent_mind import main
    main()
