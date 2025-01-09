"""对话管理API工具模块，提供对话的创建、查询和过滤等功能。"""

from typing import Type, Optional, Dict, Any, Union
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, ValidationError
from src.opera_service.api.models import DialogueForCreation, DialogueForFilter
from .base_api_tool import BaseApiTool


class DialogueToolSchema(BaseModel):
    """Dialogue工具的基础输入模式"""
    action: str = Field(..., description="操作类型: create/get/get_all/get_filtered/get_latest_index")
    opera_id: UUID = Field(..., description="Opera的UUID")
    dialogue_index: Optional[int] = Field(None, description="对话索引，仅用于get操作")
    data: Optional[Union[Dict[str, Any], DialogueForCreation, DialogueForFilter]] = Field(
        None,
        description="""对话的数据，根据action类型使用不同的数据模型:
        - create: 使用DialogueForCreation模型
        - get_filtered: 使用DialogueForFilter模型
        """
    )

    @field_validator('data')
    @classmethod
    def validate_data(cls, v, values):
        action = values.data.get('action')
        if not v:
            return v

        try:
            if action == 'create':
                return DialogueForCreation(**v)
            elif action == 'get_filtered':
                return DialogueForFilter(**v)
            return v
        except ValidationError as e:
            raise ValueError(f"数据验证失败: {str(e)}") from e


class DialogueTool(BaseApiTool):
    name: str = "Dialogue Manager"
    description: str = """管理对话的通用工具，支持创建、查询操作。
    注意必选字段不可遗漏。
    示例输入:
    1. 创建对话: {
        'action': 'create',
        'opera_id': 'uuid',
        'data': {
            'is_stage_index_null': false,
            'staff_id': 'uuid',
            'is_narratage': false,
            'is_whisper': false,
            'text': '对话内容',
            'tags': 'tag1,tag2',
            'mentioned_staff_ids': ['uuid1', 'uuid2']
        }
    }
    2. 获取所有对话: {
        'action': 'get_all', 
        'opera_id': 'uuid'
    }
    3. 获取单个对话: {
        'action': 'get', 
        'opera_id': 'uuid', 
        'dialogue_index': 1
    }
    4. 条件过滤查询对话: {
        'action': 'get_filtered',
        'opera_id': 'uuid',
        'data': {
            'index_not_before': 1,
            'index_not_after': 10,
            'top_limit': 100,
            'stage_index': 1,
            'includes_stage_index_null': true,
            'includes_narratage': true,
            'includes_for_staff_id_only': 'uuid',
            'includes_staff_id_null': true
        }
    }
    5. 获取最新对话索引: {
        'action': 'get_latest_index',
        'opera_id': 'uuid'
    }
    """
    args_schema: Type[BaseModel] = DialogueToolSchema

    def _get_base_url(self, opera_id: UUID) -> str:
        """获取基础URL"""
        return f"http://opera.nti56.com/Opera/{opera_id}/Dialogue"

    def _run(self, *args, **kwargs) -> str:
        try:
            # 如果输入是字符串，尝试解析为字典
            if isinstance(kwargs, str):
                import json
                kwargs = json.loads(kwargs)

            action = kwargs.get("action")
            opera_id = kwargs.get("opera_id")
            dialogue_index = kwargs.get("dialogue_index")
            data = kwargs.get("data")

            base_url = self._get_base_url(opera_id)

            if action == "get_all":
                result = self._make_request("GET", base_url)
                return f"状态码: {result['status_code']}, 详细内容: {str(result['data'])}"

            elif action == "get":
                if dialogue_index is None:
                    raise ValueError("获取对话需要提供dialogue_index")
                result = self._make_request("GET", f"{base_url}/{dialogue_index}")
                return f"状态码: {result['status_code']}, 详细内容: {str(result['data'])}"

            elif action == "get_filtered":
                if not data:
                    raise ValueError("过滤查询对话需要提供filter数据")
                result = self._make_request("POST", f"{base_url}/Get", json=data.model_dump(by_alias=True))
                return f"状态码: {result['status_code']}, 详细内容: {str(result['data'])}"

            elif action == "create":
                if not data:
                    raise ValueError("创建对话需要提供data")
                result = self._make_request("POST", base_url, json=data.model_dump(by_alias=True))
                return f"状态码: {result['status_code']}, 详细内容: {str(result['data'])}"

            elif action == "get_latest_index":
                result = self._make_request("GET", f"{base_url}/LatestIndex")
                return f"状态码: {result['status_code']}, 详细内容: {str(result['data'])}"

            else:
                raise ValueError(f"不支持的操作: {action}")

        except Exception as e:
            return f"操作失败: {str(e)}"


_SHARED_DIALOGUE_TOOL = DialogueTool()
