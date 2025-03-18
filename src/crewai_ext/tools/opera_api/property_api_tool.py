"""Opera属性管理API工具类

此模块提供了Opera属性管理相关的API调用功能，包括获取所有属性、获取指定属性和更新属性等操作。
"""

from typing import Type, Optional, Dict, Any, Union
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, ValidationError

from src.opera_service.api.models import OperaPropertyForUpdate
from .base_api_tool import BaseApiTool


class PropertyToolSchema(BaseModel):
    """Property工具的基础输入模式"""
    action: str = Field(..., description="操作类型: get_all/get_by_key/update")
    opera_id: UUID = Field(..., description="Opera的UUID")
    key: Optional[str] = Field(None, description="属性键名，用于get_by_key操作")
    force: Optional[bool] = Field(None, description="是否强制穿透缓存，从数据库读取")
    data: Optional[Union[Dict[str, Any], OperaPropertyForUpdate]] = Field(
        None,
        description="属性更新数据，用于update操作"
    )

    @field_validator('data')
    @classmethod
    def validate_data(cls, v, values):
        if not v:
            return v

        action = values.data.get('action')
        try:
            if action == 'update':
                return OperaPropertyForUpdate(**v)
            return v
        except ValidationError as e:
            raise ValueError(f"数据验证失败: {str(e)}") from e


class PropertyTool(BaseApiTool):
    name: str = "Property Manager"
    description: str = """管理Opera属性的通用工具，支持获取所有属性、获取指定属性和更新属性操作。
    
    示例输入:
    1. 获取所有属性: {
        'action': 'get_all',
        'opera_id': 'uuid',
        'force': true  # 可选
    }
    2. 获取指定属性: {
        'action': 'get_by_key',
        'opera_id': 'uuid',
        'key': 'property_key',
        'force': true  # 可选
    }
    3. 更新属性: {
        'action': 'update',
        'opera_id': 'uuid',
        'data': {
            'properties': {'key1': 'value1'},  # 可选，要更新或新增的属性
            'properties_to_remove': ['key2']   # 可选，要删除的属性
        }
    }
    """
    args_schema: Type[BaseModel] = PropertyToolSchema

    def _get_base_url(self, opera_id: UUID) -> str:
        """获取基础URL"""
        return f"{self._get_api_base_url()}/Opera/{opera_id}/Property"

    def _run(self, *args, **kwargs) -> str:
        try:
            # 如果输入是字符串，尝试解析为字典
            if isinstance(kwargs, str):
                import json
                kwargs = json.loads(kwargs)

            action = kwargs.get("action")
            opera_id = kwargs.get("opera_id")
            key = kwargs.get("key")
            force = kwargs.get("force")
            data = kwargs.get("data")

            base_url = self._get_base_url(opera_id)
            params = {"force": force} if force is not None else None

            if action == "get_all":
                result = self._make_request("GET", base_url, params=params)
                return f"状态码: {result['status_code']}, 详细内容: {str(result['data'])}"

            elif action == "get_by_key":
                if not key:
                    raise ValueError("获取指定属性需要提供key")
                params = {"key": key} if not params else {**params, "key": key}
                result = self._make_request("GET", f"{base_url}/ByKey", params=params)
                
                if result['status_code'] == 204:
                    return "状态码: 204, 属性不存在"
                    
                return f"状态码: {result['status_code']}, 详细内容: {str(result['data'])}"

            elif action == "update":
                if not data:
                    raise ValueError("更新属性需要提供data")
                result = self._make_request(
                    "PUT",
                    base_url,
                    json=data.model_dump(by_alias=True)
                )
                return f"状态码: {result['status_code']}, " + (
                    "属性更新成功" if result['status_code'] == 204 else f"详细内容: {str(result['data'])}")

            else:
                raise ValueError(f"不支持的操作: {action}")

        except Exception as e:
            return f"操作失败: {str(e)}" 