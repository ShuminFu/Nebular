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
    DIRECT_CREATION = 7  # 跳过对话池分析，在OPERA系统中创建资源

class ProcessingStatus(IntEnum):
    """处理状态枚举"""
    PENDING = 1
    PROCESSING = 2
    COMPLETED = 3
    FAILED = 4


# MIME类型配置
MIME_TYPE_MAPPING = {
    "text/plain": [".txt", ".log", ".ini", ".conf"],
    "text/x-python": [".py"],
    "text/javascript": [".js"],
    "text/html": [".html", ".htm"],
    "text/css": [".css"],
    "application/json": [".json"],
    "application/xml": [".xml"],
    "text/markdown": [".md"],
    "text/x-yaml": [".yml", ".yaml"]
}

# 扩展名到MIME类型的反向映射
EXT_TO_MIME_TYPE = {
    ext.lstrip('.'): mime_type
    for mime_type, exts in MIME_TYPE_MAPPING.items()
    for ext in exts
}
