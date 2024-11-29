from typing import Type, Optional, Dict, Any, Union
from uuid import UUID
import httpx
from pydantic import BaseModel, Field, field_validator, ValidationError
from Opera.FastAPI.models import Opera, OperaForCreation, OperaForUpdate, OperaWithMaintenanceState
from crewai_tools.tools.base_tool import BaseTool


class OperaToolSchema(BaseModel):
    """Opera工具的基础输入模式"""
    action: str = Field(..., description="操作类型: create/get/get_all/update/delete")
    opera_id: Optional[UUID] = Field(None, 
                                   description="Opera的UUID，用于get/update/delete操作")
    parent_id: Optional[UUID] = Field(None, 
                                    description="父Opera ID，用于get_all操作时筛选")
    data: Optional[Union[Dict[str, Any], OperaForCreation, OperaForUpdate]] = Field(
        None,
        description="""Opera的数据，根据action类型使用不同的数据模型:
        - create: 使用OperaForCreation模型 {
            name: str,
            description?: str,
            parentId?: UUID,
            databaseName?: str
        }
        - update: 使用OperaForUpdate模型 {
            name?: str,
            isDescriptionUpdated: bool,
            description?: str
        }
        """
    )

    @field_validator('data')
    def validate_data(cls, v, values):
        action = values.data.get('action')
        if not v:
            return v

        try:
            if action == 'create':
                return OperaForCreation(**v)
            elif action == 'update':
                return OperaForUpdate(**v)
            return v
        except ValidationError as e:
            raise ValueError(f"数据验证失败: {str(e)}")


class OperaTool(BaseTool):
    name: str = "Opera Manager"
    description: str = """管理Opera的通用工具，支持创建、查询、更新和删除操作。
    
    示例输入:
    1. 创建Opera: {
        'action': 'create', 
        'data': {
            'name': '新Opera', 
            'description': '描述',
            'parentId': 'uuid',  # 可选
            'databaseName': 'db_name'  # 可选，会自动生成
        }
    }
    2. 获取所有Opera: {
        'action': 'get_all',
        'parent_id': 'uuid'  # 可选，不指定时返回根节点Opera
    }
    3. 获取单个Opera: {
        'action': 'get', 
        'opera_id': 'uuid'
    }
    4. 更新Opera: {
        'action': 'update', 
        'opera_id': 'uuid', 
        'data': {
            'name': '新名称',  # 可选
            'isDescriptionUpdated': True,
            'description': '新描述'  # 如果isDescriptionUpdated为True则必填
        }
    }    
    5. 删除Opera: {
        'action': 'delete', 
        'opera_id': 'uuid'
    }
    """
    args_schema: Type[BaseModel] = OperaToolSchema
    base_url: str = "http://opera.nti56.com/Opera"

    def _make_request(self, method: str, url: str, json=None, params=None) -> dict:
        """发送HTTP请求的通用方法"""
        with httpx.Client() as client:
            response = client.request(method, url, json=json, params=params)
            response.raise_for_status()
            return {
                'status_code': response.status_code,
                'data': response.json() if response.text else None
            }

    def _run(self, **kwargs) -> str:
        try:
            # 如果输入是字符串，尝试解析为字典
            if isinstance(kwargs, str):
                import json
                kwargs = json.loads(kwargs)

            action = kwargs.get("action")
            opera_id = kwargs.get("opera_id")
            parent_id = kwargs.get("parent_id")
            data = kwargs.get("data")

            if action == "get_all":
                params = {"parent_id": parent_id} if parent_id else None
                result = self._make_request("GET", self.base_url, params=params)
                return f"状态码: {result['status_code']}, 数据: {str(result['data'])}"

            elif action == "get":
                if not opera_id:
                    raise ValueError("获取Opera需要提供opera_id")
                result = self._make_request("GET", f"{self.base_url}/{opera_id}")
                return f"状态码: {result['status_code']}, 数据: {str(result['data'])}"

            elif action == "create":
                if not data:
                    raise ValueError("创建Opera需要提供data")
                result = self._make_request("POST", self.base_url, json=data.model_dump())
                return f"状态码: {result['status_code']}, 数据: {str(result['data'])}"

            elif action == "update":
                if not opera_id or not data:
                    raise ValueError("更新Opera需要提供opera_id和data")
                result = self._make_request(
                    "PUT",
                    f"{self.base_url}/{opera_id}",
                    json=data.model_dump(by_alias=True)
                )
                return f"状态码: {result['status_code']}, " + ("Opera更新成功" if result['data'] is None else f"数据: {str(result['data'])}")

            elif action == "delete":
                if not opera_id:
                    raise ValueError("删除Opera需要提供opera_id")
                result = self._make_request("DELETE", f"{self.base_url}/{opera_id}")
                return f"状态码: {result['status_code']}, Opera删除成功"

            else:
                raise ValueError(f"不支持的操作: {action}")

        except Exception as e:
            return f"操作失败: {str(e)}" 