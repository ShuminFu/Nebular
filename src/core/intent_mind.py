"""Opera SignalR Bot对话处理器的实现。

负责将Staff的对话转换为任务并管理任务队列。
主要用于CrewManager和CrewRunner的对话处理和任务管理的桥接。
"""

from typing import Set, Dict, Optional, Union, List, TYPE_CHECKING
from uuid import UUID
import json
import re
import random

from src.core.dialogue.pools import DialoguePool
from src.core.dialogue.models import ProcessingDialogue
from src.core.dialogue.enums import DialoguePriority, DialogueType, ProcessingStatus, MIME_TYPE_MAPPING
from src.core.task_utils import BotTask, BotTaskQueue, TaskType, TaskPriority
from src.opera_service.signalr_client.opera_signalr_client import MessageReceivedArgs
from src.core.parser.code_resource_parser import CodeResourceParser
from src.crewai_ext.crew_bases.cr_matcher_crewbase import CRMatcherCrew

if TYPE_CHECKING:
    from src.core.crew_process import CrewProcessInfo


class IntentMind:
    """Bot的意图处理器

    负责：
    1. 接收和管理Staff的对话
    2. 分析对话意图（通过DialoguePool的分析器）
    3. 转换为任务并进行调度
    4. 识别和处理代码资源
    """

    def __init__(self, task_queue: BotTaskQueue, crew_processes: Optional[Dict[UUID, "CrewProcessInfo"]] = None):
        self.dialogue_pool = DialoguePool()
        self.task_queue = task_queue  # 使用外部传入的任务队列
        self.crew_processes = crew_processes
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
        7. 代码资源（通过tags判断）
        8. 迭代对话（通过tags判断）
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
            if "skip_analysis" and "code_resource" in message.tags.lower():
                return DialogueType.DIRECT_CREATION
            if "system" in message.tags.lower():
                return DialogueType.SYSTEM
            if "task_callback" in message.tags.lower():
                return DialogueType.SYSTEM
            # 检查代码相关标签
            if any(tag in message.tags.lower() for tag in ["code_resource", "code", "script", "function"]):
                return DialogueType.CODE_RESOURCE
            if any(tag in message.tags.lower() for tag in ["ResourcesMentionedFromViewer", "ResourcesForIncarnating", "ResourcesForViewing", "SelectedTextsFromViewer"]):
                return DialogueType.ITERATION

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
        if any(marker in text for marker in ["@file:", "@description:", "@tags:", "@version:"]):
            return True

        # 常见编程语言关键字
        keywords = r"\b(def|class|function|import|from|return|if|else|for|while|try|catch|async|await)\b"

        # 函数或类定义模式
        definitions = r"(def\s+\w+\s*\(|class\s+\w+\s*[:\(])"

        # 代码注释模式
        comments = r"(#.*$|\/\/.*$|\/\*[\s\S]*?\*\/)"

        # 代码缩进结构
        indentation = r"^\s{2,}.*$"

        # 检查文本是否符合上述任一模式
        patterns = [keywords, definitions, comments, indentation]
        text_lines = text.split("\n")

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

    def _select_code_resource_handler(self, dialogue: ProcessingDialogue, code_details: str) -> Optional[UUID]:
        """选择合适的CR来处理代码生成任务"""
        # 新增根据opera_id选择CR的逻辑
        if self.crew_processes and dialogue.opera_id:
            candidate_staffs = []
            
            # 遍历所有CrewProcess查找匹配opera_id的配置
            for process_info in self.crew_processes.values():
                if dialogue.opera_id in process_info.opera_ids:
                    # 获取该opera_id对应的staff列表
                    staff_id = process_info.staff_ids.get(dialogue.opera_id[0], None)
                    crew_config = process_info.crew_config["agents"]
                    if staff_id:
                        candidate_staff = f"{staff_id}:{crew_config}"
                        candidate_staffs.append(candidate_staff)
            
            if candidate_staff:
                result = CRMatcherCrew.kickoff(inputs={
                    "code_details": code_details,
                    "candidate_staffs": candidate_staffs,
                })
                selected_cr = json.loads(result.raw)
                return UUID(selected_cr)
        else:    
            # 获取所有可能的CR（排除CM自己）
            crs = [staff_id for staff_id in dialogue.receiver_staff_ids if staff_id != dialogue.sender_staff_id]

            if not crs:
                return None
            elif len(crs) == 1:
                return crs[0]
            
            # 保留原有随机选择作为fallback
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

    async def _create_task_from_dialogue(self, dialogue: ProcessingDialogue) -> Union[BotTask, List[BotTask]]:
        """从对话创建任务，支持返回多个任务"""
        # 只有非DIRECT_CREATION类型的对话才需要更新状态
        if dialogue.type != DialogueType.DIRECT_CREATION and dialogue.dialogue_index is not None:
            await self.dialogue_pool.update_dialogue_status(dialogue.dialogue_index, ProcessingStatus.PROCESSING)

        # 基于对话类型进行初步的任务类型判断
        task_type = TaskType.CONVERSATION  # 默认为基础对话处理
        task_priority = dialogue.priority

        # 获取主题信息
        topic_info = dialogue.context.conversation_state.get("topic", {})
        topic_id = topic_info.get("id")
        topic_type = topic_info.get("type")

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
            },
            "opera_id": str(dialogue.opera_id) if dialogue.opera_id else None,
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

        # 对于DIRECT_CREATION类型，直接解析代码资源并创建任务
        elif dialogue.type == DialogueType.DIRECT_CREATION:
            task_type = TaskType.RESOURCE_CREATION
            task_priority = TaskPriority.HIGH

            # 解析代码资源内容
            metadata, code_content = self._parse_code_resource(dialogue.text)

            # 从metadata中获取file_path
            file_path = metadata.get("file")
            if not file_path:
                # 如果metadata中没有file_path，使用默认值
                file_path = "src/code/main.py"

            # 从tags中解析topic信息
            if dialogue.tags:
                tags = dialogue.tags.lower().split(";")
                for tag in tags:
                    if tag.startswith("topic_id:"):
                        topic_id = tag.replace("topic_id:", "").strip()
                        break

            # 如果存在topic_id，直接将其添加到file_path前面
            # if topic_id:
            #     import os
            #     file_path = os.path.join(topic_id, file_path)

            # 根据文件扩展名确定mime_type
            ext = "." + file_path.split(".")[-1].lower()
            # 在MIME_TYPE_MAPPING中查找对应的mime_type
            for mime_type, extensions in MIME_TYPE_MAPPING.items():
                if ext in extensions:
                    break
            else:
                mime_type = "text/plain"  # 如果没找到对应的mime_type，使用默认值

            # 更新任务参数
            task_parameters.update({
                "text": "",  # 不需要冗余传输
                "resource_type": "code",
                "file_path": file_path,
                "mime_type": mime_type,
                "description": metadata.get("description", ""),
                "tags": self._parse_tags(metadata.get("tags")),
                "code_content": code_content.strip(),  # 确保去除首尾空白字符
            })

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
                    resources = [
                        {
                            "file_path": code_details.get(
                                "file_path",
                                f"src/{code_details.get('type', 'python').lower()}/main.{code_details.get('type', 'py').lower()}",
                            ),
                            "type": code_details.get("type", "python"),
                            "mime_type": "text/x-python",
                        }
                    ]

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
                                    "intent": related_dialogue.intent_analysis.model_dump()
                                    if related_dialogue.intent_analysis
                                    else None,
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
                                "resources": resources,  # 包含所有资源信息，便于理解文件间关系
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
                                "related_dialogues": related_dialogues,
                            },
                            "opera_id": str(dialogue.opera_id) if dialogue.opera_id else None,
                            "parent_topic_id": "0",
                        },
                        source_dialogue_index=dialogue.dialogue_index,
                        source_staff_id=dialogue.sender_staff_id,
                        response_staff_id=selected_cr
                        if selected_cr
                        else (dialogue.receiver_staff_ids[0] if dialogue.receiver_staff_ids else None),
                        topic_id=topic_id,
                        topic_type=topic_type,
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

        elif dialogue.type == DialogueType.ITERATION:
            # 从tags中解析version_id作为父级话题ID
            version_id = parse_version_id(self._parse_tags(dialogue.tags))
            
            task_parameters.update({
                "parent_topic_id": version_id,
                "text": dialogue.text,
                "tags": dialogue.tags
            })
            task_type = TaskType.RESOURCE_ITERATION
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
            response_staff_id = (
                selected_cr if selected_cr else (dialogue.receiver_staff_ids[0] if dialogue.receiver_staff_ids else None)
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
            source_staff_id=dialogue.sender_staff_id,  # 设置源Staff ID为对话的发送者
            topic_id=topic_id,
            topic_type=topic_type,
        )

        return task

    async def _preprocess_message(self, message: MessageReceivedArgs) -> Optional[int]:
        """处理单个对话, 这一步步骤主要是确定对话的优先级和类型, 并创建ProcessingDialogue对象加入对话池。

        Args:
            message: MessageReceivedArgs对象

        Returns:
            Optional[int]: 对话索引，如果是DIRECT_CREATION类型则返回None
        """
        # 确定优先级和类型
        priority = self._determine_dialogue_priority(message)
        dialogue_type = self._determine_dialogue_type(message)

        # 创建ProcessingDialogue
        processing_dialogue = ProcessingDialogue.from_message_args(message, priority=priority, dialogue_type=dialogue_type)

        # 如果是DIRECT_CREATION类型，直接返回None，不添加到对话池
        if dialogue_type == DialogueType.DIRECT_CREATION:
            return None

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
        # 1. 预处理对话
        dialogue_index = await self._preprocess_message(message)

        # 捷径：特定的对话类型没有加入对话池的返回值，直接创建任务并添加到队列
        if dialogue_index is None:
            # 创建临时ProcessingDialogue用于任务创建
            priority = self._determine_dialogue_priority(message)
            dialogue_type = self._determine_dialogue_type(message)
            temp_dialogue = ProcessingDialogue.from_message_args(message, priority=priority, dialogue_type=dialogue_type)
            task = await self._create_task_from_dialogue(temp_dialogue)
            await self.task_queue.add_task(task)
            return

        # 2. 分析对话 - analysis flow
        await self.dialogue_pool.analyze_dialogues()

        # 3. 创建任务, 从对话池中获取对话来创建任务
        analyzed_dialogue = self.dialogue_pool.get_dialogue(dialogue_index)
        if analyzed_dialogue and analyzed_dialogue.status == ProcessingStatus.PENDING:
            task = await self._create_task_from_dialogue(analyzed_dialogue)
            await self.task_queue.add_task(task)
            # 更新对话状态为已完成
            await self.dialogue_pool.update_dialogue_status(dialogue_index, ProcessingStatus.COMPLETED)

    def get_staff_dialogues(self, staff_id: UUID) -> Set[int]:
        """获取对话发送人为指定Staff的所有对话索引"""
        return self.staff_dialogues.get(staff_id, set())

    def get_dialogue_pool(self) -> DialoguePool:
        """获取当前对话池"""
        return self.dialogue_pool

def parse_version_id(tags: List[str]) -> Optional[str]:
    """从tags中解析version_id"""
    for tag in tags:
        try:
            tag_data = json.loads(tag)
            # 优先从SelectedTextsFromViewer获取version_id
            if "SelectedTextsFromViewer" in tag_data:
                for item in tag_data["SelectedTextsFromViewer"]:
                    if "VersionId" in item:
                        return item["VersionId"]
            # 其次从ResourcesForViewing获取
            if "ResourcesForViewing" in tag_data:
                return tag_data["ResourcesForViewing"].get("VersionId")
            # 最后从ResourcesForIncarnating获取
            if "ResourcesForIncarnating" in tag_data:
                return tag_data["ResourcesForIncarnating"].get("VersionId")
        except (json.JSONDecodeError, TypeError):
            continue
    return None
        
if __name__ == "__main__":
    from src.core.tests.test_intent_mind import main

    main()
