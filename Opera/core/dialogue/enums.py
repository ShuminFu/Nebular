from enum import IntEnum


class DialoguePriority(IntEnum):
    """对话优先级枚举"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


class DialogueType(IntEnum):
    """对话类型枚举 - 基于对话的基础特征进行分类"""
    NORMAL = 1      # 普通对话
    WHISPER = 2     # 私密对话（悄悄话）
    MENTION = 3     # 提及对话（@某人）
    NARRATAGE = 4   # 旁白
    SYSTEM = 5      # 系统消息
    CODE_RESOURCE = 6  # 代码资源


class ProcessingStatus(IntEnum):
    """处理状态枚举"""
    PENDING = 1
    PROCESSING = 2
    COMPLETED = 3
    FAILED = 4
