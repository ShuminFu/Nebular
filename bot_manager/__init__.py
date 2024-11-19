"""
BotManager - A unified bot management system
"""

from .core.interfaces import IBot, IBotAdapter
from .core.factory import BotFactory

__version__ = "0.1.0"
__all__ = ["IBot", "IBotAdapter", "BotFactory"] 