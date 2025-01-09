""" Opera SignalR Bot对话处理器的实现。

负责将Staff的对话转换为任务并管理任务队列。
主要用于CrewManager和CrewRunner的对话处理和任务管理的桥接。
"""

from typing import Set, Dict, Optional, Union, List
from uuid import UUID
import json
import re
import random

from src.core.dialogue.pools import DialoguePool
from src.core.dialogue.models import ProcessingDialogue
from src.core.dialogue.enums import DialoguePriority, DialogueType, ProcessingStatus, MIME_TYPE_MAPPING
from src.core.task_utils import BotTask, BotTaskQueue, TaskType, TaskPriority
from src.opera_service.signalr_client.opera_signalr_client import MessageReceivedArgs
from src.core.code_resource_parser import CodeResourceParser


class IntentMind:
    """Bot的意图处理器

    负责：
    1. 接收和管理Staff的对话
    2. 分析对话意图（通过DialoguePool的分析器）
    3. 转换为任务并进行调度
    4. 识别和处理代码资源
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
            # 代码资源相关的对话优先级提高
            if any(tag in message.tags.lower() for tag in ["code_resource", "code", "script", "function"]):
                return DialoguePriority.HIGH
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
                return DialogueType.SYSTEM
            # 检查代码相关标签
            if any(tag in message.tags.lower() for tag in ["code_resource", "code", "script", "function"]):
                return DialogueType.CODE_RESOURCE

        # 如果消息内容看起来像代码，将其标记为代码资源
        if self._is_code_content(message.text):
            return DialogueType.CODE_RESOURCE

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

    def _is_code_content(self, text: str) -> bool:
        """判断文本是否包含代码内容
        
        通过以下特征判断：
        1. 包含常见的编程语言关键字
        2. 包含函数/类定义
        3. 包含代码注释
        4. 具有代码缩进结构
        5. 包含特定的代码标记（如@file, @description等）
        
        Args:
            text: 要分析的文本
            
        Returns:
            bool: 是否是代码内容
        """
        if not text:
            return False

        # 检查是否已经是标准格式的代码资源
        if any(marker in text for marker in ['@file:', '@description:', '@tags:', '@version:']):
            return True

        # 常见编程语言关键字
        keywords = r'\b(def|class|function|import|from|return|if|else|for|while|try|catch|async|await)\b'

        # 函数或类定义模式
        definitions = r'(def\s+\w+\s*\(|class\s+\w+\s*[:\(])'

        # 代码注释模式
        comments = r'(#.*$|\/\/.*$|\/\*[\s\S]*?\*\/)'

        # 代码缩进结构
        indentation = r'^\s{2,}.*$'

        # 检查文本是否符合上述任一模式
        patterns = [keywords, definitions, comments, indentation]
        text_lines = text.split('\n')

        # 统计符合模式的行数
        pattern_matches = 0
        for line in text_lines:
            for pattern in patterns:
                if re.search(pattern, line, re.MULTILINE):
                    pattern_matches += 1
                    break

        # 如果超过30%的行符合代码模式，则认为是代码内容
        return pattern_matches / len(text_lines) > 0.3 if text_lines else False

    def _parse_code_resource(self, content: str) -> tuple[dict, str]:
        """解析代码资源内容，使用CodeResourceParser"""
        return CodeResourceParser.parse(content)

    def _select_code_resource_handler(self, dialogue: ProcessingDialogue, code_details: dict) -> Optional[UUID]:
        """选择合适的CR来处理代码生成任务
        
        选择策略：
        1. 如果只有一个CR，直接选择
        2. 如果有多个CR，根据以下因素选择：
           - 代码类型匹配（比如Python专家）
           - 框架经验（比如pandas专家）
           - 当前任务负载
           - 历史成功率
        
        Args:
            dialogue: 当前对话
            code_details: 代码相关信息

        Returns:
            Optional[UUID]: 选中的CR的staff_id
        """
        # 获取所有可能的CR（排除CM自己）
        crs = [
            staff_id for staff_id in dialogue.receiver_staff_ids
            if staff_id != dialogue.sender_staff_id
        ]

        if not crs:
            return None
        elif len(crs) == 1:
            return crs[0]

        # TODO: 实现更复杂的CR选择逻辑
        # 1. 从staff的parameters中获取专长信息, 或者通过api接口获取他们的prompt
        # 2. 匹配代码类型和框架需求
        # 3. 考虑当前任务队列负载
        # 4. 考虑历史完成率

        # 暂时随机选择一个CR
        return random.choice(crs)

    def _parse_tags(self, tags_data: Union[str, List[str], None]) -> List[str]:
        """解析tags数据，支持字符串和列表格式

        Args:
            tags_data: 可以是字符串(如 "[tag1,tag2]" 或 "tag1,tag2")，
                      或者是字符串列表(如 ["tag1", "tag2"])，
                      或者是None

        Returns:
            List[str]: 处理后的tags列表
        """
        if not tags_data:
            return []

        if isinstance(tags_data, list):
            return [str(tag).strip() for tag in tags_data if tag]

        if isinstance(tags_data, str):
            # 移除可能存在的方括号
            cleaned = tags_data.strip("[]")
            if not cleaned:
                return []
            # 分割并清理每个tag
            return [tag.strip() for tag in cleaned.split(",") if tag.strip()]

        return []

    def _create_task_from_dialogue(self, dialogue: ProcessingDialogue) -> Union[BotTask, List[BotTask]]:
        """从对话创建任务，支持返回多个任务"""
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
            "context": {
                "stage_index": dialogue.context.stage_index,
                "related_dialogue_indices": list(dialogue.context.related_dialogue_indices),
                "conversation_state": dialogue.context.conversation_state,
                "flow": dialogue.context.conversation_state.get("flow", {}),
                "code_context": dialogue.context.conversation_state.get("code_context", {}),
                "decision_points": dialogue.context.conversation_state.get("decision_points", []),
                "topic": dialogue.context.conversation_state.get("topic", {
                    "id": None,
                    "type": None,
                    "name": None,
                    "last_updated": None
                })
            },
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

        elif dialogue.type == DialogueType.CODE_RESOURCE:
            # 从intent_analysis中获取代码生成相关信息
            if dialogue.intent_analysis and dialogue.intent_analysis.parameters.get("is_code_request"):
                task_type = TaskType.RESOURCE_GENERATION
                task_priority = TaskPriority.HIGH
                code_details = dialogue.intent_analysis.parameters.get("code_details", {})

                # 获取需要生成的文件列表
                resources = code_details.get("resources", [])
                if not resources:
                    # 如果没有明确指定resources，创建默认的单文件资源
                    resources = [{
                        "file_path": code_details.get("file_path", f"src/{code_details.get('type', 'python').lower()}/main.{code_details.get('type', 'py').lower()}"),
                        "type": code_details.get("type", "python"),
                        "mime_type": "text/x-python"
                    }]

                # 为每个文件创建独立的CODE_GENERATION任务
                tasks = []
                for resource in resources:
                    # 选择合适的CR来处理代码生成任务
                    selected_cr = self._select_code_resource_handler(dialogue, code_details)

                    # 获取相关对话的内容
                    related_dialogues = []
                    if dialogue.context and dialogue.context.related_dialogue_indices:
                        for idx in dialogue.context.related_dialogue_indices:
                            related_dialogue = self.dialogue_pool.get_dialogue(idx)
                            if related_dialogue:
                                related_dialogues.append({
                                    "index": related_dialogue.dialogue_index,
                                    "text": related_dialogue.text,
                                    "type": related_dialogue.type.name,
                                    "tags": related_dialogue.tags,
                                    "intent": related_dialogue.intent_analysis.model_dump() if related_dialogue.intent_analysis else None,
                                })

                    task = BotTask(
                        type=TaskType.RESOURCE_GENERATION,
                        priority=TaskPriority.HIGH,
                        description=f"生成代码文件: {resource['file_path']}",
                        parameters={
                            "file_path": resource["file_path"],
                            "file_type": resource["type"],
                            "mime_type": resource["mime_type"],
                            "description": resource.get("description", ""),
                            "references": resource.get("references", []),
                            "code_details": {  # 保留完整的代码细节，便于上下文理解
                                "project_type": code_details.get("project_type"),
                                "project_description": code_details.get("project_description"),
                                "requirements": code_details.get("requirements", []),
                                "frameworks": code_details.get("frameworks", []),
                                "resources": resources  # 包含所有资源信息，便于理解文件间关系
                            },
                            "dialogue_context": {
                                "text": dialogue.text,
                                "type": dialogue.type.name,
                                "tags": dialogue.tags,
                                "intent": dialogue.intent_analysis.model_dump() if dialogue.intent_analysis else None,
                                "stage_index": dialogue.context.stage_index,
                                "related_dialogue_indices": list(dialogue.context.related_dialogue_indices),
                                "conversation_state": dialogue.context.conversation_state,
                                "flow": dialogue.context.conversation_state.get("flow", {}),
                                "code_context": dialogue.context.conversation_state.get("code_context", {}),
                                "decision_points": dialogue.context.conversation_state.get("decision_points", []),
                                "topic": dialogue.context.conversation_state.get("topic", {
                                    "id": None,
                                    "type": None,
                                    "name": None,
                                    "last_updated": None
                                }),
                                "related_dialogues": related_dialogues
                            },
                            "opera_id": str(dialogue.opera_id) if dialogue.opera_id else None
                        },
                        source_dialogue_index=dialogue.dialogue_index,
                        source_staff_id=dialogue.sender_staff_id,
                        response_staff_id=selected_cr if selected_cr else (
                            dialogue.receiver_staff_ids[0] if dialogue.receiver_staff_ids else None
                        )
                    )
                    tasks.append(task)
                return tasks
            else:
                # 如果不是代码生成请求，则作为普通资源创建处理
                task_type = TaskType.RESOURCE_CREATION

                # 解析代码资源内容
                metadata, code_content = self._parse_code_resource(dialogue.text)

                # 从metadata中获取file_path和mime_type
                file_path = metadata.get("file")
                if not file_path:
                    # 如果metadata中没有file_path，尝试从code_details中获取
                    if dialogue.intent_analysis and dialogue.intent_analysis.parameters.get("code_details"):
                        code_details = dialogue.intent_analysis.parameters["code_details"]
                        resources = code_details.get("resources", [])
                        if resources:
                            file_path = resources[0].get("file_path")

                # 根据文件扩展名确定mime_type
                if file_path:
                    ext = "." + file_path.split(".")[-1].lower()
                    # 在MIME_TYPE_MAPPING中查找对应的mime_type
                    for mime_type, extensions in MIME_TYPE_MAPPING.items():
                        if ext in extensions:
                            break
                    else:
                        mime_type = "text/plain"  # 如果没找到对应的mime_type，使用默认值
                else:
                    mime_type = "text/plain"

                # 更新任务参数
                task_parameters.update({
                    "resource_type": "code",
                    "file_path": file_path,
                    "mime_type": mime_type,
                    "description": metadata.get("description", ""),
                    "tags": self._parse_tags(metadata.get("tags")),
                    "code_content": code_content.strip(),  # 确保去除首尾空白字符
                })

        elif dialogue.type == DialogueType.SYSTEM:
            task_type = TaskType.SYSTEM
        elif dialogue.type in [DialogueType.WHISPER, DialogueType.MENTION]:
            task_type = TaskType.CHAT_RESPONSE
        elif dialogue.type == DialogueType.NARRATAGE:
            task_type = TaskType.ANALYSIS

        # 创建单个任务
        # 如果是代码相关的任务，需要选择合适的CR
        if task_type in [TaskType.RESOURCE_CREATION, TaskType.RESOURCE_GENERATION]:
            selected_cr = self._select_code_resource_handler(dialogue, task_parameters.get("code_details", {}))
            response_staff_id = selected_cr if selected_cr else (
                dialogue.receiver_staff_ids[0] if dialogue.receiver_staff_ids else None
            )
        else:
            response_staff_id = dialogue.receiver_staff_ids[0] if dialogue.receiver_staff_ids else None

        task = BotTask(
            priority=task_priority,
            type=task_type,
            description=f"Process dialogue {dialogue.dialogue_index} from staff {dialogue.sender_staff_id}",
            parameters=task_parameters,
            source_dialogue_index=dialogue.dialogue_index,
            response_staff_id=response_staff_id,
            source_staff_id=dialogue.sender_staff_id  # 设置源Staff ID为对话的发送者
        )

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

        # 分析对话 - 使用DialoguePool的分析器
        self.dialogue_pool.analyze_dialogues()

        # 从对话池中获取已分析的对话来创建任务
        analyzed_dialogue = self.dialogue_pool.get_dialogue(dialogue_index)
        if analyzed_dialogue and analyzed_dialogue.status == ProcessingStatus.PENDING:
            task = self._create_task_from_dialogue(analyzed_dialogue)
            await self.task_queue.add_task(task)
            # 更新对话状态为已完成
            self.dialogue_pool.update_dialogue_status(dialogue_index, ProcessingStatus.COMPLETED)

    def get_staff_dialogues(self, staff_id: UUID) -> Set[int]:
        """获取对话发送人为指定Staff的所有对话索引"""
        return self.staff_dialogues.get(staff_id, set())

    def get_dialogue_pool(self) -> DialoguePool:
        """获取当前对话池"""
        return self.dialogue_pool


if __name__ == '__main__':
    from src.core.tests.test_intent_mind import main
    main()
