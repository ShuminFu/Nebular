"""Opera SignalR 任务队列的数据模型定义。

包含了所有与任务管理相关的Pydantic模型。
主要用于CrewManager和CrewRunner的任务管理。

JSON示例:
{
    "TaskQueue": {
        "Tasks": [
            {
                "Id": "550e8400-e29b-41d4-a716-446655440002",
                "CreatedAt": "2024-01-28T12:00:00Z",
                "StartedAt": null,
                "CompletedAt": null,
                "Priority": 2,
                "Type": 1,
                "Status": 1,
                "Dependencies": [],
                "Data": {
                    "Description": "分析用户提供的代码",
                    "Parameters": {
                        "language": "python",
                        "codeSnippet": "def hello(): print('world')"
                    },
                    "SourceDialogueIndex": 1,
                    "AssignedAgent": "code_analysis_agent",
                    "Context": {
                        "projectType": "python"
                    }
                },
                "Progress": 0,
                "Result": null,
                "ErrorMessage": null,
                "RetryCount": 0
            }
        ],
        "Statistics": {
            "PendingCount": 1,
            "RunningCount": 0,
            "CompletedCount": 0,
            "FailedCount": 0,
            "BlockedCount": 0
        }
    }
}
"""

from pydantic import Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from uuid import UUID
from enum import IntEnum

from Opera.FastAPI.models import CamelBaseModel
from Opera.Signalr.models.dialogue_queue import QueuedDialogue


class TaskPriority(IntEnum):
    """任务优先级枚举"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


class TaskType(IntEnum):
    """任务类型枚举"""
    CONVERSATION = 1
    ANALYSIS = 2
    ACTION = 3
    SYSTEM = 4


class TaskStatus(IntEnum):
    """任务状态枚举"""
    PENDING = 1
    RUNNING = 2
    COMPLETED = 3
    FAILED = 4
    BLOCKED = 5


class TaskData(CamelBaseModel):
    """任务数据模型
    
    示例:
    {
        "Description": "分析用户提供的代码",
        "Parameters": {
            "language": "python",
            "codeSnippet": "def hello(): print('world')"
        },
        "SourceDialogueIndex": 1,
        "AssignedAgent": "code_analysis_agent",
        "Context": {
            "projectType": "python"
        }
    }
    """
    description: str = Field(..., description="任务描述")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="任务参数")
    source_dialogue_index: Optional[int] = Field(default=None, description="关联的对话索引")
    assigned_agent: Optional[str] = Field(default=None, description="负责的Agent")
    context: Optional[Dict[str, Any]] = Field(default=None, description="任务上下文")


class Task(CamelBaseModel):
    """任务模型
    
    示例:
    {
        "Id": "550e8400-e29b-41d4-a716-446655440002",
        "CreatedAt": "2024-01-28T12:00:00Z",
        "StartedAt": null,
        "CompletedAt": null,
        "Priority": 2,
        "Type": 1,
        "Status": 1,
        "Dependencies": [],
        "Data": {
            "Description": "分析用户提供的代码",
            "Parameters": {
                "language": "python",
                "codeSnippet": "def hello(): print('world')"
            },
            "SourceDialogueIndex": 1,
            "AssignedAgent": "code_analysis_agent",
            "Context": {
                "projectType": "python"
            }
        },
        "Progress": 0,
        "Result": null,
        "ErrorMessage": null,
        "RetryCount": 0
    }
    """
    id: UUID = Field(..., description="任务唯一标识")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone(timedelta(hours=8))), 
        description="创建时间 (UTC+8)"
    )
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    priority: TaskPriority = Field(default=TaskPriority.NORMAL, description="任务优先级")
    type: TaskType = Field(..., description="任务类型")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")
    dependencies: List[UUID] = Field(default_factory=list, description="依赖任务ID列表")
    data: TaskData = Field(..., description="任务数据")
    progress: int = Field(default=0, description="任务进度(0-100)")
    result: Optional[Any] = Field(default=None, description="任务结果")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    retry_count: int = Field(default=0, description="重试次数")


class TaskQueue(CamelBaseModel):
    """任务队列模型
    
    示例:
    {
        "Tasks": [...],
        "Statistics": {
            "PendingCount": 1,
            "RunningCount": 0,
            "CompletedCount": 0,
            "FailedCount": 0,
            "BlockedCount": 0
        }
    }
    """
    tasks: List[Task] = Field(default_factory=list, description="任务列表")
    statistics: Dict[str, int] = Field(
        default_factory=lambda: {
            "pending_count": 0,
            "running_count": 0,
            "completed_count": 0,
            "failed_count": 0,
            "blocked_count": 0
        },
        description="队列统计信息"
    ) 


class TaskQueueManager:
    def __init__(self, bot_id: UUID):
        self.bot_id = bot_id
        self.task_queue = TaskQueue()
        
    def create_task_from_queued_dialogue(self, queued_dialogue: QueuedDialogue) -> Task:
        """将QueuedDialogue转换为Task"""
        task_data = TaskData(
            description=f"Process dialogue from staff {queued_dialogue.staff_id}",
            parameters={
                "dialogue_index": queued_dialogue.dialogue_index,
                "staff_id": str(queued_dialogue.staff_id),
                "intent": queued_dialogue.metadata.intent_analysis
            },
            source_dialogue_index=queued_dialogue.dialogue_index,
            context=queued_dialogue.metadata.context.model_dump()
        )
        
        task = Task(
            id=UUID(),
            priority=TaskPriority(queued_dialogue.priority.value),  # 保持优先级一致
            type=TaskType.CONVERSATION,  # 默认为对话类型
            data=task_data
        )
        return task
    
    def add_queued_dialogue(self, queued_dialogue: QueuedDialogue) -> None:
        """添加QueuedDialogue到任务队列"""
        if queued_dialogue.bot_id != self.bot_id:
            raise ValueError("QueuedDialogue belongs to different bot")
            
        task = self.create_task_from_queued_dialogue(queued_dialogue)
        self.task_queue.tasks.append(task)
        self.update_statistics()
        
    def update_statistics(self) -> None:
        """更新任务队列统计信息"""
        stats = {
            "pending_count": 0,
            "running_count": 0,
            "completed_count": 0,
            "failed_count": 0,
            "blocked_count": 0
        }
        
        for task in self.task_queue.tasks:
            if task.status == TaskStatus.PENDING:
                stats["pending_count"] += 1
            elif task.status == TaskStatus.RUNNING:
                stats["running_count"] += 1
            elif task.status == TaskStatus.COMPLETED:
                stats["completed_count"] += 1
            elif task.status == TaskStatus.FAILED:
                stats["failed_count"] += 1
            elif task.status == TaskStatus.BLOCKED:
                stats["blocked_count"] += 1
                
        self.task_queue.statistics = stats
