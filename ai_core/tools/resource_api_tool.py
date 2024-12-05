"""资源管理工具，提供资源的创建、查询、更新、删除和下载功能。"""

from typing import Type, Optional, Dict, Any, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, ValidationError
from Opera.FastAPI.models import Resource, ResourceForCreation, ResourceForUpdate, ResourceForFilter
from .base_api_tool import BaseApiTool


class ResourceToolSchema(BaseModel):
    """Resource工具的基础输入模式"""
    action: str = Field(
        ..., description="操作类型: create/get/get_all/get_filtered/update/delete/download")
    opera_id: UUID = Field(..., description="Opera的UUID")
    resource_id: Optional[UUID] = Field(
        None, description="资源ID，用于get/update/delete/download操作")
    data: Optional[Union[Dict[str, Any], ResourceForCreation, ResourceForUpdate, ResourceForFilter]] = Field(
        None,
        description="""资源的数据，根据action类型使用不同的数据模型:
        - create: 使用ResourceForCreation模型
        - update: 使用ResourceForUpdate模型
        - get_filtered: 使用ResourceForFilter模型
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
                return ResourceForCreation(**v)
            elif action == 'update':
                return ResourceForUpdate(**v)
            elif action == 'get_filtered':
                return ResourceForFilter(**v)
            return v
        except ValidationError as e:
            raise ValueError(f"数据验证失败: {str(e)}") from e


class ResourceTool(BaseApiTool):
    name: str = "Resource Manager"
    description: str = """管理资源文件的通用工具，支持创建、查询、更新、删除和下载操作。
    
    示例输入:
    1. 创建资源: {
        'action': 'create',
        'opera_id': 'uuid',
        'data': {
            # ResourceForCreation的字段
        }
    }
    2. 获取所有资源: {
        'action': 'get_all', 
        'opera_id': 'uuid'
    }
    3. 获取单个资源: {
        'action': 'get', 
        'opera_id': 'uuid', 
        'resource_id': 'uuid'
    }
    4. 条件过滤查询资源: {
        'action': 'get_filtered',
        'opera_id': 'uuid',
        'data': {
            # ResourceForFilter的字段
        }
    }
    5. 更新资源: {
        'action': 'update',
        'opera_id': 'uuid',
        'resource_id': 'uuid',
        'data': {
            # ResourceForUpdate的字段
        }
    }
    6. 删除资源: {
        'action': 'delete',
        'opera_id': 'uuid',
        'resource_id': 'uuid'
    }
    7. 下载资源: {
        'action': 'download',
        'opera_id': 'uuid',
        'resource_id': 'uuid'
    }
    """
    args_schema: Type[BaseModel] = ResourceToolSchema

    def _get_base_url(self, opera_id: UUID) -> str:
        """获取基础URL"""
        return f"http://opera.nti56.com/Opera/{opera_id}/Resource"

    def _run(self, *args, **kwargs) -> str:
        try:
            # 如果输入是字符串，尝试解析为字典
            if isinstance(kwargs, str):
                import json
                kwargs = json.loads(kwargs)

            action = kwargs.get("action")
            opera_id = kwargs.get("opera_id")
            resource_id = kwargs.get("resource_id")
            data = kwargs.get("data")

            base_url = self._get_base_url(opera_id)

            if action == "get_all":
                result = self._make_request("GET", base_url)
                return [Resource(**item) for item in result['data']]

            elif action == "get":
                if not resource_id:
                    raise ValueError("获取资源需要提供resource_id")
                result = self._make_request("GET", f"{base_url}/{resource_id}")
                return Resource(**result['data'])

            elif action == "get_filtered":
                if not data:
                    raise ValueError("过滤查询资源需要提供filter数据")
                result = self._make_request(
                    "POST",
                    f"{base_url}/Get",
                    json=data.model_dump(exclude_none=True)
                )
                return [Resource(**item) for item in result['data']]

            elif action == "create":
                if not data:
                    raise ValueError("创建资源需要提供data")
                result = self._make_request(
                    "POST",
                    base_url,
                    json=data.model_dump()
                )
                return Resource(**result['data'])

            elif action == "update":
                if not resource_id or not data:
                    raise ValueError("更新资源需要提供resource_id和data")
                self._make_request(
                    "PUT",
                    f"{base_url}/{resource_id}",
                    json=data.model_dump(exclude_none=True)
                )
                return None

            elif action == "delete":
                if not resource_id:
                    raise ValueError("删除资源需要提供resource_id")
                self._make_request("DELETE", f"{base_url}/{resource_id}")
                return None

            elif action == "download":
                if not resource_id:
                    raise ValueError("下载资源需要提供resource_id")
                # 注意：下载操作可能需要特殊处理，因为基类的_make_request假设响应是JSON
                # 这里可能需要在基类中添加支持或使用自定义实现
                result = self._make_request(
                    "GET", f"{base_url}/{resource_id}/Download")
                return result['data']

            else:
                raise ValueError(f"不支持的操作: {action}")

        except Exception as e:
            return f"操作失败: {str(e)}"
