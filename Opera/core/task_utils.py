"""Opera SignalR 任务队列的数据模型定义。"""

from pydantic import Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
from enum import IntEnum

from Opera.FastAPI.models import CamelBaseModel


class TaskPriority(IntEnum):
    """任务优先级枚举"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


class TaskType(IntEnum):
    """任务类型枚举"""
        # 基础对话任务
    CONVERSATION = 10  # 基础对话处理，不一定需要回复，比如CrewRunner仅回复被Mentioned或者Whispered的对话
    CHAT_PLANNING = 11  # 对话策略规划
    CHAT_RESPONSE = 12  # 对话响应生成
    
    # 分析类任务
    ANALYSIS = 20  # 基础分析
    INTENT_ANALYSIS = 21  # 意图分析
    CONTEXT_ANALYSIS = 22  # 上下文分析，比如需要额外的RAG BOT/SEARCH BOT的帮助来收集上下文
    
    # 执行类任务
    ACTION = 30  # 基础动作
    TOOL_EXECUTION = 31  # 工具调用
    API_CALL = 32  # API调用
    
    # 管理类任务
    SYSTEM = 40  # 系统任务
    CREW_LIFECYCLE = 41  # CrewRunner的生命周期管理
    STAGE_MANAGEMENT = 42  # Opera Stage 管理
    ROLE_ASSIGNMENT = 43  # 发言角色分配


class TaskStatus(IntEnum):
    """任务状态枚举"""
    PENDING = 1
    RUNNING = 2
    COMPLETED = 3
    FAILED = 4
    BLOCKED = 5


class BotTask(CamelBaseModel):
    """任务模型"""
    id: UUID = Field(default_factory=lambda: UUID(int=uuid4().int), description="任务唯一标识")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone(timedelta(hours=8))), 
        description="创建时间 (UTC+8)"
    )
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    
    # 任务基本信息
    priority: TaskPriority = Field(default=TaskPriority.NORMAL, description="任务优先级")
    type: TaskType = Field(..., description="任务类型")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")
    
    # 任务内容
    description: str = Field(..., description="任务描述")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="任务参数")
    
    # 来源信息
    source_dialogue_index: Optional[int] = Field(default=None, description="源对话索引")
    source_staff_id: Optional[UUID] = Field(default=None, description="源Staff ID")
    
    # 执行信息
    progress: int = Field(default=0, description="任务进度(0-100)")
    result: Optional[Any] = Field(default=None, description="任务结果")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    retry_count: int = Field(default=0, description="重试次数")
    last_retry_at: Optional[datetime] = Field(default=None, description="最后重试时间")


class BotTaskQueue(CamelBaseModel):
    """任务队列模型"""
    tasks: List[BotTask] = Field(default_factory=list, description="任务列表")
    status_counter: Dict[str, int] = Field(
        default_factory=lambda: {status.name.lower(): 0 for status in TaskStatus},
        description="状态计数器"
    )
    bot_id: UUID = Field(..., description="Bot ID")

    async def _persist_to_api(self) -> None:
        """将任务队列状态持久化到API
        
        TODO: 持久化API调用逻辑
        - 使用bot_id作为API调用的参数
        - 可以调用TaskTool进行批量更新
        - 需要将BotTask转换为API所需的格式
        - 处理可能的API调用失败情况
        """
        pass

    @classmethod
    def create(cls, bot_id: UUID, **kwargs) -> "BotTaskQueue":
        """创建任务队列的工厂方法

        Args:
            bot_id: Bot ID
            **kwargs: 其他参数

        Returns:
            BotTaskQueue: 新创建的任务队列实例
        """
        return cls(bot_id=bot_id, **kwargs)

    @classmethod
    async def restore_from_api(cls, bot_id: UUID, **kwargs) -> "BotTaskQueue":
        """从API恢复任务队列状态的工厂方法

        TODO: 实现从API恢复数据的逻辑
        - 使用bot_id从API获取持久化的任务数据
        - 将API数据转换为BotTask对象
        - 重建任务队列的状态计数器
        - 处理可能的API调用失败情况
        - 考虑任务状态的有效性（是否需要重置某些状态）
        - 考虑是否需要增量恢复机制

        Args:
            bot_id: Bot ID
            **kwargs: 配置参数，可能包括时间范围、过滤条件等

        Returns:
            BotTaskQueue: 恢复的任务队列实例
        """
        # 创建一个新的任务队列实例
        queue = cls(bot_id=bot_id, **kwargs)

        # 从API获取持久化的任务数据
        # restored_data = await task_api.get_persisted_tasks(bot_id=bot_id, **kwargs)

        # 将API数据转换为BotTask对象
        # queue.tasks = [BotTask(**data) for data in restored_data]

        # 重建状态计数器
        # queue.status_counter = Counter(task.status.name.lower() for task in queue.tasks)

        return queue

    async def add_task(self, task: BotTask) -> None:
        """添加任务并更新计数器"""
        self.tasks.append(task)
        self.status_counter[task.status.name.lower()] += 1
        # 添加任务后持久化
        await self._persist_to_api()
    
    async def update_task_status(self, task_id: UUID, new_status: TaskStatus) -> None:
        """更新任务状态并维护计数器"""
        for task in self.tasks:
            if task.id == task_id:
                old_status = task.status
                task.status = new_status
                
                # 更新时间戳
                if new_status == TaskStatus.RUNNING:
                    task.started_at = datetime.now(timezone(timedelta(hours=8)))
                elif new_status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    task.completed_at = datetime.now(timezone(timedelta(hours=8)))
                
                # 更新计数器
                self.status_counter[old_status.name.lower()] -= 1
                self.status_counter[new_status.name.lower()] += 1
                # 状态更新后持久化
                await self._persist_to_api()
                break
    
    def get_next_task(self) -> Optional[BotTask]:
        """获取下一个待处理的任务（按优先级排序，同优先级按创建时间FIFO）"""
        pending_tasks = [
            task for task in self.tasks 
            if task.status == TaskStatus.PENDING
        ]
        if not pending_tasks:
            return None
        
        return max(pending_tasks, key=lambda x: (x.priority, x.created_at.timestamp()))
