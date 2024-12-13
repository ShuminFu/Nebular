"""Opera SignalR 对话队列和任务队列的数据模型定义。

包含了所有与对话处理和任务管理相关的Pydantic模型。
主要用于CrewManager和CrewRunner的消息处理和任务管理。

JSON示例:
1. 对话队列 (存储在Staff的Parameters字段):
{
    "DialogueQueueManager": {
        "Pending": [
            {
                "Index": 1,
                "Time": "2024-01-28T12:00:00Z",
                "StageIndex": null,
                "StaffId": "550e8400-e29b-41d4-a716-446655440000",
                "IsNarratage": false,
                "IsWhisper": false,
                "Text": "请帮我分析这段代码",
                "Tags": "code,analysis",
                "MentionedStaffIds": [],
                "Priority": 2,
                "Type": 1,
                "Status": 1,
                "Metadata": {
                    "Source": "user_123",
                    "Context": {
                        "previousDialogueIndex": 0
                    },
                    "IntentAnalysis": {
                        "intent": "code_analysis",
                        "confidence": 0.95
                    }
                },
                "RetryCount": 0,
                "ErrorMessage": null
            }
        ],
        "Processing": [],
        "Completed": [],
        "QueueStats": {
            "PendingCount": 1,
            "ProcessingCount": 0,
            "CompletedCount": 0
        }
    }
}

"""

from pydantic import Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from uuid import UUID
from enum import IntEnum

from Opera.FastAPI.models import CamelBaseModel, Dialogue


class DialoguePriority(IntEnum):
    """对话优先级枚举"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


class DialogueType(IntEnum):
    """对话类型枚举"""
    TEXT = 1
    COMMAND = 2
    QUERY = 3
    SYSTEM = 4


class DialogueStatus(IntEnum):
    """对话状态枚举"""
    PENDING = 1
    PROCESSING = 2
    COMPLETED = 3
    FAILED = 4


class DialogueSource(CamelBaseModel):
    """对话来源信息模型"""
    type: str = Field(..., description="来源类型，如 'staff', 'system', 'user'")
    identifier: str = Field(..., description="来源标识，如staff_name/system_module/user_id等")
    additional_info: Optional[Dict[str, Any]] = Field(default=None, description="额外的来源信息")


class DialogueContext(CamelBaseModel):
    """对话上下文模型"""
    related_dialogue_indices: List[int] = Field(default_factory=list, description="相关对话索引列表")
    related_task_ids: List[UUID] = Field(default_factory=list, description="相关任务ID列表")
    conversation_state: Optional[Dict[str, Any]] = Field(default=None, description="对话状态信息")
    memory: Optional[Dict[str, Any]] = Field(default=None, description="对话记忆信息")


class QueuedDialogueMetadata(CamelBaseModel):
    """队列中对话的元数据模型
    
    示例:
    {
        "Source": {
            "Type": "staff",
            "Identifier": "assistant_alpha",
            "AdditionalInfo": {
                "role": "code_analyzer",
                "department": "tech_support"
            }
        },
        "Context": {
            "RelatedDialogueIndices": [1, 2, 3],
            "RelatedTaskIds": ["550e8400-e29b-41d4-a716-446655440002"],
            "ConversationState": {
                "current_topic": "code_analysis",
                "awaiting_user_input": false
            },
            "Memory": {
                "last_analyzed_file": "main.py",
                "user_preferences": {
                    "language": "python"
                }
            }
        },
        "IntentAnalysis": {
            "intent": "code_analysis",
            "confidence": 0.95,
            "extractedParams": {
                "language": "python",
                "action": "analyze"
            }
        }
    }
    """
    source: DialogueSource = Field(..., description="对话来源信息")
    context: DialogueContext = Field(..., description="对话上下文信息")
    intent_analysis: Optional[Dict[str, Any]] = Field(default=None, description="意图分析结果, 对应到Task中的expected output")


class QueuedDialogue(CamelBaseModel):
    """队列中的对话引用模型，只存储必要的处理信息
    
    示例:
    {
        "DialogueIndex": 1,
        "BotId": "550e8400-e29b-41d4-a716-446655440000",
        "StaffId": "550e8400-e29b-41d4-a716-446655440001",
        "Priority": 2,
        "Type": 1,
        "Status": 1,
        "Metadata": {
            "Source": "user_123",
            "IntentAnalysis": {
                "intent": "code_analysis",
                "confidence": 0.95,
                "extractedParams": {
                    "language": "python",
                    "action": "analyze"
                }
            },
            "Context": {
                "previousDialogueIndices": [0],
                "relatedTaskIds": ["550e8400-e29b-41d4-a716-446655440002"]
            }
        },
        "RetryCount": 0,
        "ErrorMessage": null
    }
    """
    dialogue_index: int = Field(..., description="原始对话索引")
    bot_id: UUID = Field(..., description="所属Bot ID")
    staff_id: UUID = Field(..., description="发起Staff ID")
    priority: DialoguePriority = Field(default=DialoguePriority.NORMAL, description="处理优先级")
    type: DialogueType = Field(..., description="对话类型")
    status: DialogueStatus = Field(default=DialogueStatus.PENDING, description="处理状态")
    metadata: QueuedDialogueMetadata = Field(..., description="处理元数据")
    retry_count: int = Field(default=0, description="重试次数")
    error_message: Optional[str] = Field(default=None, description="错误信息")


class DialogueQueueManager(CamelBaseModel):
    """对话队列管理器模型
    
    示例:
    {
        "Pending": [...],
        "Processing": [...],
        "Completed": [...],
        "QueueStats": {
            "PendingCount": 1,
            "ProcessingCount": 0,
            "CompletedCount": 0
        }
    }
    """
    pending: List[QueuedDialogue] = Field(default_factory=list, description="待处理对话")
    processing: List[QueuedDialogue] = Field(default_factory=list, description="处理中对话")
    completed: List[QueuedDialogue] = Field(default_factory=list, description="已完成对话")
    queue_stats: Dict[str, int] = Field(
        default_factory=lambda: {"pending_count": 0, "processing_count": 0, "completed_count": 0},
        description="队列统计信息"
    )
