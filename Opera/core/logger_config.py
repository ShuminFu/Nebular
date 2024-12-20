import sys
from loguru import logger
from typing import Optional
from uuid import uuid4


def setup_logger(name: str = None, log_file: str = None):
    """设置通用的日志配置

    Args:
        name: 模块名称，用于日志标识
        log_file: 日志文件路径，如果不指定则只输出到控制台
    """
    # 移除默认的处理器
    logger.remove()

    # 控制台输出配置
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<yellow>[{extra[trace_id]}]</yellow> "
            "{message}"
        ),
        level="INFO",
    )

    # 如果指定了日志文件，添加文件输出
    if log_file:
        logger.add(
            log_file,
            rotation="500 MB",
            retention="10 days",
            compression="zip",
            format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
                "{name}:{function}:{line} - [{extra[trace_id]}] {message}"
            ),
            level="DEBUG",
        )

    # 设置默认trace_id
    return logger.bind(trace_id=None)


def get_logger(name: str = None, log_file: Optional[str] = None):
    """获取一个预配置的logger实例

    Args:
        name: 模块名称
        log_file: 日志文件路径（可选）

    Returns:
        配置好的logger实例
    """
    return setup_logger(name, log_file)


def get_logger_with_trace_id():
    """获取一个带有新trace_id的logger实例"""
    return logger.bind(trace_id=str(uuid4()))
