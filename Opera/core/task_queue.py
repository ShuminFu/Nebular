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

    def add_task(self, task: BotTask) -> None:
        """添加任务并更新计数器"""
        self.tasks.append(task)
        self.status_counter[task.status.name.lower()] += 1
    
    def update_task_status(self, task_id: UUID, new_status: TaskStatus) -> None:
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
                break
    
    def get_next_pending_task(self) -> Optional[BotTask]:
        """获取下一个待处理的任务（按优先级排序）"""
        pending_tasks = [
            task for task in self.tasks 
            if task.status == TaskStatus.PENDING
        ]
        if not pending_tasks:
            return None
        
        return max(pending_tasks, key=lambda x: (x.priority, -x.created_at.timestamp()))
