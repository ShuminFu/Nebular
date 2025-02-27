from dataclasses import dataclass
from typing import Dict, Set, Optional, List, Callable, Awaitable
from uuid import UUID

from src.core.task_utils import BotTask, TaskStatus, TaskType

@dataclass
class VersionMeta:
    parent_version: Optional[str]  # 父版本ID
    modified_files: List[Dict[str, str]]  # 本次修改的文件列表，包含file_path和resource_id
    description: str  # 修改原因/用户反馈/任务描述
    current_files: List[Dict[str, str]]  # 当前版本的完整文件列表，包含file_path和resource_id


# TODO:delta changes fields for diff modification such as line 1-20

@dataclass
class TopicInfo:
    """主题信息"""
    tasks: Set[UUID]  # 任务ID集合
    type: str  # 主题类型
    status: str  # 主题状态
    opera_id: str  # Opera ID
    current_version: Optional[VersionMeta] = None  # 当前版本
    expected_creation_count: int = 0  # 由generation任务预报的预期创建任务数量
    actual_creation_count: int = 0  # 实际添加到tracker的创建任务数量
    completed_creation_count: int = 0  # 已完成的创建任务数量


# 定义回调类型
TopicCompletionCallback = Callable[[str, str], Awaitable[None]]  # topic_id, opera_id


class TopicTracker:
    """主题追踪器，负责管理主题状态和任务关系"""

    def __init__(self):
        self.topics: Dict[str, TopicInfo] = {}
        self._completion_callbacks: List[TopicCompletionCallback] = []
        self._completed_tasks: Dict[str, Set[UUID]] = {}  # topic_id -> completed task ids
        self._pending_resource_tasks: Dict[UUID, str] = {}  # task_id -> file_path，存储等待resource_id的任务

    def on_completion(self, callback: TopicCompletionCallback):
        """注册主题完成回调"""
        self._completion_callbacks.append(callback)

    def add_task(self, task: BotTask):
        """添加任务到主题"""
        if not task.topic_id:
            return

        if task.topic_id not in self.topics:
            self.topics[task.topic_id] = TopicInfo(
                tasks=set(), type=task.topic_type, status="active", opera_id=task.parameters.get("opera_id"), current_version=None
            )
            # 初始化版本（当parent_topic_id为0时）
            if parent_topic_id := task.parameters.get("parent_topic_id"):
                parent_version = None if parent_topic_id == "0" else parent_topic_id
                self.topics[task.topic_id].current_version = VersionMeta(
                    parent_version=parent_version, modified_files=[], description="Initial version", current_files=[]
                )
            self._completed_tasks[task.topic_id] = set()

        topic = self.topics[task.topic_id]
        topic.tasks.add(task.id)

        # 更新任务计数：根据任务类型更新对应的计数器
        if task.type == TaskType.RESOURCE_GENERATION:
            # 对于RESOURCE_GENERATION任务，增加预期创建任务数量
            # 可以从task.parameters中获取预期创建的文件数量，如果没有就默认加1
            expected_files_count = task.parameters.get("expected_files_count", 1)
            topic.expected_creation_count += expected_files_count
        elif task.type == TaskType.RESOURCE_CREATION:
            # 对于RESOURCE_CREATION任务，增加实际创建任务数量
            topic.actual_creation_count += 1

        # 处理文件路径更新
        file_path = task.parameters.get("file_path")
        resource_id = task.parameters.get("resource_id")

        # 对于资源创建任务，先记录file_path，等任务完成后再更新resource_id
        if task.type == TaskType.RESOURCE_CREATION and file_path:
            self._pending_resource_tasks[task.id] = file_path
            # 如果已有resource_id，直接更新；否则等待任务完成后更新
            if resource_id:
                self._update_file_mapping(topic, file_path, resource_id)
        # 对于非资源创建任务，直接更新file_path和resource_id的映射
        elif file_path and resource_id:
            self._update_file_mapping(topic, file_path, resource_id)

    def _update_file_mapping(self, topic: TopicInfo, file_path: str, resource_id: str):
        """更新文件路径与资源ID的映射关系"""
        file_entry = {"file_path": file_path, "resource_id": resource_id}

        # 更新当前版本，添加空值检查
        if topic.current_version is not None:
            # 检查是否已存在相同file_path的条目
            for files_list in [topic.current_version.modified_files, topic.current_version.current_files]:
                for i, entry in enumerate(files_list):
                    if entry["file_path"] == file_path:
                        # 如果存在，更新resource_id
                        files_list[i]["resource_id"] = resource_id
                        break
                else:
                    # 如果不存在，添加新条目
                    files_list.append(file_entry)
        else:
            # 如果current_version为None，则初始化一个默认版本
            topic.current_version = VersionMeta(
                parent_version=None,
                modified_files=[file_entry],
                description="Auto-initialized version",
                current_files=[file_entry],
            )

    async def update_task_status(self, task_id: UUID, status: TaskStatus, task: Optional[BotTask] = None):
        """
        更新任务状态并检查主题完成情况

        Args:
            task_id: 任务ID
            status: 新状态
            task: 可选的完整任务对象，用于获取任务结果
        """
        # 查找任务所属的主题
        topic_id = None
        for tid, topic in self.topics.items():
            if task_id in topic.tasks:
                topic_id = tid
                break

        if not topic_id:
            return

        # 获取任务类型
        task_type = None
        if task is not None:
            task_type = task.type

        # 如果是资源创建任务且已完成，处理resource_id更新
        if status == TaskStatus.COMPLETED and task_id in self._pending_resource_tasks:
            # 通过topic_id找到任务所属的主题
            topic = self.topics[topic_id]

            # 如果传入了任务对象，直接使用
            if task is not None:
                if (result := task.result) and isinstance(result, dict) and (resource_id := result.get("resource_id")):
                    file_path = self._pending_resource_tasks[task_id]
                    # 更新文件映射
                    self._update_file_mapping(topic, file_path, resource_id)
                    # 从待处理列表中移除
                    self._pending_resource_tasks.pop(task_id)

        # 如果任务完成，记录并更新计数
        if status == TaskStatus.COMPLETED:
            topic = self.topics[topic_id]
            self._completed_tasks[topic_id].add(task_id)

            # 如果是RESOURCE_CREATION任务，增加已完成创建任务计数并检查完成情况
            if task_type == TaskType.RESOURCE_CREATION:
                topic.completed_creation_count += 1
                # 只有CREATION类任务完成才会触发主题完成检查
                await self._check_topic_completion(topic_id)
            # 对于其他类型的任务（如RESOURCE_GENERATION），只记录完成但不检查主题完成情况

    async def _check_topic_completion(self, topic_id: str):
        """检查主题是否全部完成"""
        topic = self.topics.get(topic_id)
        if not topic or topic.status != 'active':
            return

        # 新的完成逻辑：检查已完成的创建任务数量是否达到预期数量
        # 首先检查是否有预期数量
        if topic.expected_creation_count > 0:
            # 如果有预期数量，检查已完成的创建任务是否达到预期数量
            if topic.completed_creation_count >= topic.expected_creation_count:
                # 达到预期数量，标记为完成
                await self._complete_topic(topic_id, topic)
        # 如果没有预期数量或预期数量为0，检查是否所有实际添加的创建任务都已完成
        elif topic.actual_creation_count > 0 and topic.completed_creation_count >= topic.actual_creation_count:
            # 所有实际添加的创建任务都已完成，标记为完成
            await self._complete_topic(topic_id, topic)
        # 保留原有的检查逻辑作为兼容性后备
        elif topic.tasks == self._completed_tasks[topic_id]:
            # 所有任务都已完成，标记为完成
            await self._complete_topic(topic_id, topic)

    async def _complete_topic(self, topic_id: str, topic: TopicInfo):
        """将主题标记为完成并触发回调"""
        # 通知所有回调
        for callback in self._completion_callbacks:
            await callback(topic_id, topic.opera_id)

        # 更新主题状态
        topic.status = "completed"

    def get_topic_info(self, topic_id: str) -> Optional[TopicInfo]:
        """获取主题信息"""
        return self.topics.get(topic_id)
