from dataclasses import dataclass, field
from typing import Dict, Set, Optional, List, Callable, Awaitable
from uuid import UUID

from src.core.task_utils import BotTask, TaskStatus

@dataclass
class VersionMeta:
    parent_version: Optional[str]  # 父版本ID
    modified_files: List[str]  # 本次涉及的的文件路径url
    description: str  # 修改原因/用户反馈/任务描述
    current_files: List[str]  # 当前版本的完整文件路径url列表


# TODO:delta changes fields for diff modification such as line 1-20

@dataclass
class TopicInfo:
    """主题信息"""
    tasks: Set[UUID]  # 任务ID集合
    type: str  # 主题类型
    status: str  # 主题状态
    opera_id: str  # Opera ID
    version_tree: List[VersionMeta] = field(default_factory=list)  # 新增版本历史


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
                tasks=set(), type=task.topic_type, status="active", opera_id=task.parameters.get("opera_id"), version_tree=[]
            )
            self._completed_tasks[task.topic_id] = set()

        topic = self.topics[task.topic_id]
        topic.tasks.add(task.id)

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
                await callback(topic_id, topic.type, topic.opera_id)

            # 更新主题状态
            topic.status = 'completed'

    def get_topic_info(self, topic_id: str) -> Optional[TopicInfo]:
        """获取主题信息"""
        return self.topics.get(topic_id)
