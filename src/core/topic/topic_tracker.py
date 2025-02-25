from dataclasses import dataclass
from typing import Dict, Set, Optional, List, Callable, Awaitable
from uuid import UUID

from src.core.task_utils import BotTask, TaskStatus

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


# 定义回调类型
TopicCompletionCallback = Callable[[str, str, str], Awaitable[None]]  # topic_id, type, opera_id


class TopicTracker:
    """主题追踪器，负责管理主题状态和任务关系"""

    def __init__(self):
        self.topics: Dict[str, TopicInfo] = {}
        self._completion_callbacks: List[TopicCompletionCallback] = []
        self._completed_tasks: Dict[str, Set[UUID]] = {}  # topic_id -> completed task ids

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

        # 处理文件路径更新
        if (file_path := task.parameters.get("file_path")) and (resource_id := task.parameters.get("resource_id")):
            file_entry = {"file_path": file_path, "resource_id": resource_id}
            
            # 更新当前版本
            if not any(f["file_path"] == file_path for f in topic.current_version.modified_files):
                topic.current_version.modified_files.append(file_entry)
            if not any(f["file_path"] == file_path for f in topic.current_version.current_files):
                topic.current_version.current_files.append(file_entry)

    async def update_task_status(self, task_id: UUID, status: TaskStatus):
        """更新任务状态并检查主题完成情况"""
        # 查找任务所属的主题
        topic_id = None
        for tid, topic in self.topics.items():
            if task_id in topic.tasks:
                topic_id = tid
                break

        if not topic_id:
            return

        # 如果任务完成，记录并检查主题是否全部完成
        if status == TaskStatus.COMPLETED:
            self._completed_tasks[topic_id].add(task_id)
            await self._check_topic_completion(topic_id)

    async def _check_topic_completion(self, topic_id: str):
        """检查主题是否全部完成"""
        topic = self.topics.get(topic_id)
        if not topic or topic.status != 'active':
            return

        # 检查所有任务是否都已完成
        if topic.tasks == self._completed_tasks[topic_id]:
            # 通知所有回调
            for callback in self._completion_callbacks:
                await callback(topic_id, topic.opera_id)

            # 更新主题状态
            topic.status = 'completed'

    def get_topic_info(self, topic_id: str) -> Optional[TopicInfo]:
        """获取主题信息"""
        return self.topics.get(topic_id)
