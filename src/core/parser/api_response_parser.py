import ast
import json
from typing import List, Dict, Any, TYPE_CHECKING, Set, Union



if TYPE_CHECKING:
    from src.core.dialogue.models import ProcessingDialogue
    from src.core.task_utils import BotTaskQueue


class ApiResponseParser:
    """API响应解析器"""

    @staticmethod
    def parse_response(response: str) -> tuple[int, dict]:
        """解析API响应
        
        Args:
            response: API返回的字符串响应
            
        Returns:
            tuple: (状态码, 解析后的数据字典)
            
        Note:
            - 如果响应包含错误信息（如302重定向），将返回 (-1, {})
            - 正常响应应包含 "状态码: " 和 "详细内容: " 字段
        """
        try:
            # 检查是否包含错误信息
            if "操作失败" in response or "Redirect response" in response:
                return -1, {}

            status_start = response.find("状态码: ") + len("状态码: ")
            if status_start < len("状态码: "):  # 没找到状态码
                return -1, {}

            status_end = response.find(", ", status_start)
            if status_end == -1:  # 没找到分隔符
                return -1, {}

            status_code = int(response[status_start:status_end])

            data_start = response.find("详细内容: ") + len("详细内容: ")
            if data_start < len("详细内容: "):  # 没找到详细内容
                return status_code, {}

            data = ast.literal_eval(response[data_start:])
            return status_code, data

        except (ValueError, SyntaxError, AttributeError) as e:
            # 任何解析错误都返回 -1 和空字典
            return -1, {}

    @staticmethod
    def parse_default_tags(bot_data: dict) -> dict:
        """解析Bot的defaultTags
        
        Args:
            bot_data: Bot数据字典
            
        Returns:
            dict: 解析后的defaultTags字典
        """
        default_tags_str = bot_data.get("defaultTags") or "{}"
        if isinstance(default_tags_str, dict):
            return default_tags_str

        try:
            # 首先尝试使用ast.literal_eval
            return ast.literal_eval(default_tags_str)
        except (ValueError, SyntaxError):
            try:
                # 如果ast.literal_eval失败，尝试使用json.loads
                return json.loads(default_tags_str)
            except json.JSONDecodeError:
                # 如果两种方法都失败，返回空字典
                return {}

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
    def get_task_queue(default_tags: dict) -> "BotTaskQueue":
        """从defaultTags中获取任务队列
        
        Args:
            default_tags: defaultTags字典
            
        Returns:
            BotTaskQueue: 任务队列
        """
        from src.core.task_utils import BotTaskQueue
        return default_tags.get("TaskQueue", BotTaskQueue())

    @staticmethod
    def get_processing_dialogues(parameters: dict) -> List['ProcessingDialogue']:
        """从defaultTags中获取正在处理的对话列表
        
        Args:
            parameters: Staff的parameters字典
            
        Returns:
            list: 正在处理的对话列表
        """
        from src.core.dialogue.models import ProcessingDialogue  # noqa: F401

        return parameters.get("ProcessingDialogues", [])

    @staticmethod
    def parse_crew_output(result: Any) -> Union[Set[int], str, Dict]:
        """解析CrewOutput的通用方法
        
        Args:
            result: CrewOutput对象或其他返回值
            
        Returns:
            如果是数字集合则返回Set[int]，如果是JSON则返回Dict，否则返回字符串
        """
        try:
            # 从CrewOutput中提取实际的字符串内容
            if result and hasattr(result, 'raw'):
                content = result.raw
            else:
                content = str(result)

            # 如果内容是JSON格式的字符串（通常以```json开头）
            if content.strip().startswith('```json'):
                # 移除Markdown的JSON代码块标记
                json_str = content.strip()
                if json_str.startswith('```json\n'):
                    json_str = json_str[8:]
                if json_str.endswith('\n```'):
                    json_str = json_str[:-4]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

            # 尝试直接解析为JSON
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass

            # 如果不是JSON，按原来的逻辑处理数字集合
            related_indices = set()
            if isinstance(content, int):
                related_indices.add(content)
                return related_indices
            elif isinstance(content, str):
                if ',' in content:
                    try:
                        indices = [int(idx.strip()) for idx in content.split(',')]
                        related_indices.update(indices)
                        return related_indices
                    except ValueError:
                        return content
                else:
                    try:
                        related_indices.add(int(content))
                        return related_indices
                    except ValueError:
                        return content

            return content

        except Exception as e:
            print(f"解析CrewOutput失败: {str(e)}")
            return str(result)
