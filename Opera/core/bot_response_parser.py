import ast
from typing import List
from Opera.core.dialogue_utils import ProcessingDialogue
from Opera.core.task_queue import BotTaskQueue


class ApiResponseParser:
    """API响应解析器"""
    
    @staticmethod
    def parse_response(response: str) -> tuple[int, dict]:
        """解析API响应
        
        Args:
            response: API返回的字符串响应
            
        Returns:
            tuple: (状态码, 解析后的数据字典)
        """
        status_start = response.find("状态码: ") + len("状态码: ")
        status_end = response.find(", ", status_start)
        status_code = int(response[status_start:status_end])
        
        data_start = response.find("详细内容: ") + len("详细内容: ")
        data = ast.literal_eval(response[data_start:])
        
        return status_code, data
    
    @staticmethod
    def parse_default_tags(bot_data: dict) -> dict:
        """解析Bot的defaultTags
        
        Args:
            bot_data: Bot数据字典
            
        Returns:
            dict: 解析后的defaultTags字典
        """
        default_tags = ast.literal_eval(bot_data.get("defaultTags", "{}"))
        return default_tags
    
    @staticmethod
    def parse_parameters(bot_data: dict) -> dict:
        """解析Staff的parameters
        
        Args:
            bot_data: Bot数据字典
            
        Returns:
            dict: 解析后的parameters字典
        """
        parameters = ast.literal_eval(bot_data.get("parameters", "{}"))
        return parameters

    @staticmethod
    def get_child_bots(default_tags: dict) -> list:
        """从defaultTags中获取子Bot列表
        
        Args:
            default_tags: defaultTags字典
            
        Returns:
            list: 子Bot ID列表
        """
        return default_tags.get("ChildBots", [])

    @staticmethod
    def get_task_queue(default_tags: dict) -> BotTaskQueue:
        """从defaultTags中获取任务队列
        
        Args:
            default_tags: defaultTags字典
            
        Returns:
            BotTaskQueue: 任务队列
        """
        return default_tags.get("TaskQueue", BotTaskQueue())

    @staticmethod
    def get_processing_dialogues(parameters: dict) -> List[ProcessingDialogue]:
        """从defaultTags中获取正在处理的对话列表
        
        Args:
            parameters: Staff的parameters字典
            
        Returns:
            list: 正在处理的对话列表
        """
        return parameters.get("ProcessingDialogues", [])
