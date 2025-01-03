"""Stage管理API工具模块，提供Stage的创建、查询等功能。"""

from typing import Type, Optional, Dict, Any, Union
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, ValidationError
from src.opera_service.FastAPI.models import StageForCreation
from .base_api_tool import BaseApiTool


class StageToolSchema(BaseModel):
    """Stage工具的基础输入模式"""
    action: str = Field(..., description="操作类型: get_all/get_current/get_by_index/create")
    opera_id: UUID = Field(..., description="Opera的UUID")
    stage_index: Optional[int] = Field(None, description="场幕索引，仅用于get_by_index操作")
    force: Optional[bool] = Field(None, description="是否强制穿透缓存，仅用于get_current操作")
    data: Optional[Union[Dict[str, Any], StageForCreation]] = Field(
        None,
        description="Stage的创建数据，仅用于create操作"
    )

    @field_validator('data')
    @classmethod
    def validate_data(cls, v, values):
        if not v:
            return v

        action = values.data.get('action')
        try:
            if action == 'create':
                return StageForCreation(**v)
            return v
        except ValidationError as e:
            raise ValueError(f"数据验证失败: {str(e)}") from e


class StageTool(BaseApiTool):
    name: str = "Stage Manager"
    description: str = """管理Stage的通用工具，支持获取所有场幕、获取当前场幕、获取指定场幕和创建场幕操作。
    
    示例输入:
    1. 获取所有场幕: {
        'action': 'get_all',
        'opera_id': 'uuid'
    }
    2. 获取当前场幕: {
        'action': 'get_current',
        'opera_id': 'uuid',
        'force': true  # 可选
    }
    3. 获取指定场幕: {
        'action': 'get_by_index',
        'opera_id': 'uuid',
        'stage_index': 1
    }
    4. 创建场幕: {
        'action': 'create',
        'opera_id': 'uuid',
        'data': {
            'name': 'stage_name'
        }
    }
    """
    args_schema: Type[BaseModel] = StageToolSchema

    def _get_base_url(self, opera_id: UUID) -> str:
        """获取基础URL"""
        return f"http://opera.nti56.com/Opera/{opera_id}/Stage"

    def _run(self, *args, **kwargs) -> str:
        try:
            # 如果输入是字符串，尝试解析为字典
            if isinstance(kwargs, str):
                import json
                kwargs = json.loads(kwargs)

            action = kwargs.get("action")
            opera_id = kwargs.get("opera_id")
            stage_index = kwargs.get("stage_index")
            force = kwargs.get("force")
            data = kwargs.get("data")

            base_url = self._get_base_url(opera_id)

            if action == "get_all":
                result = self._make_request("GET", base_url)
                return f"状态码: {result['status_code']}, 详细内容: {str(result['data'])}"

            elif action == "get_current":
                params = {"force": force} if force is not None else None
                result = self._make_request("GET", f"{base_url}/Current", params=params)
                if result['status_code'] == 204:
                    return "未找到当前场幕"
                return f"状态码: {result['status_code']}, 详细内容: {str(result['data'])}"

            elif action == "get_by_index":
                if stage_index is None:
                    raise ValueError("获取指定场幕需要提供stage_index")
                result = self._make_request("GET", f"{base_url}/{stage_index}")
                return f"状态码: {result['status_code']}, 详细内容: {str(result['data'])}"

            elif action == "create":
                if not data:
                    raise ValueError("创建场幕需要提供data")
                result = self._make_request("POST", base_url, json=data.model_dump(by_alias=True))
                return f"状态码: {result['status_code']}, 详细内容: {str(result['data'])}"

            else:
                raise ValueError(f"不支持的操作: {action}")

        except Exception as e:
            return f"操作失败: {str(e)}" 