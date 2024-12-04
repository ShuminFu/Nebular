from typing import Type, Optional, Dict, Any, Union
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, ValidationError
from Opera.FastAPI.models import StaffForCreation, StaffForUpdate, StaffForFilter
from .base_api_tool import BaseApiTool


class StaffToolSchema(BaseModel):
    """Staff工具的基础输入模式"""
    action: str = Field(..., description="操作类型: create/get/get_all/update/delete/get_by_name/get_by_name_like/get_filtered")
    opera_id: UUID = Field(..., description="Opera的UUID")
    staff_id: Optional[UUID] = Field(None, description="Staff的UUID，仅用于get/update/delete操作")
    name: Optional[str] = Field(None, description="Staff名称，用于get_by_name/get_by_name_like操作")
    is_on_stage: Optional[bool] = Field(None, description="是否在台上，用于get_by_name/get_by_name_like操作的过滤")
    data: Optional[Union[Dict[str, Any], StaffForCreation, StaffForUpdate, StaffForFilter]] = Field(
        None,
        description="""Staff的数据，根据action类型使用不同的数据模型:
        - create: 使用StaffForCreation模型
        - update: 使用StaffForUpdate模型
        - get_filtered: 使用StaffForFilter模型
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
                return StaffForCreation(**v)
            elif action == 'update':
                return StaffForUpdate(**v)
            elif action == 'get_filtered':
                return StaffForFilter(**v)
            return v
        except ValidationError as e:
            raise ValueError(f"数据验证失败: {str(e)}") from e


class StaffTool(BaseApiTool):
    name: str = "Staff Manager"
    description: str = """管理Staff的通用工具，支持创建、查询、更新和删除操作。
    
    示例输入:
    1. 创建Staff: {
        'action': 'create',
        'opera_id': 'uuid',
        'data': {
            'bot_id': 'uuid',
            'name': 'staff_name',
            'parameter': '{"key": "value"}',
            'is_on_stage': true,
            'tags': 'tag1,tag2',
            'roles': 'role1,role2',
            'permissions': 'perm1,perm2'
        }
    }
    2. 获取所有Staff: {'action': 'get_all', 'opera_id': 'uuid'}
    3. 获取单个Staff: {'action': 'get', 'opera_id': 'uuid', 'staff_id': 'uuid'}
    4. 按名称获取Staff: {
        'action': 'get_by_name',
        'opera_id': 'uuid',
        'name': 'staff_name',
        'is_on_stage': true
    }
    5. 按名称模糊查询Staff: {
        'action': 'get_by_name_like',
        'opera_id': 'uuid',
        'name': 'staff',
        'is_on_stage': true
    }
    6. 条件过滤查询Staff: {
        'action': 'get_filtered',
        'opera_id': 'uuid',
        'data': {
            'bot_id': 'uuid',
            'name': 'staff_name',
            'name_like': 'staff',
            'is_on_stage': true
        }
    }
    7. 更新Staff: {
        'action': 'update',
        'opera_id': 'uuid',
        'staff_id': 'uuid',
        'data': {
            'is_on_stage': true,
            'parameter': '{"key": "new_value"}'
        }
    }
    8. 删除Staff: {'action': 'delete', 'opera_id': 'uuid', 'staff_id': 'uuid'}
    """
    args_schema: Type[BaseModel] = StaffToolSchema

    def _get_base_url(self, opera_id: UUID) -> str:
        """获取基础URL"""
        return f"http://opera.nti56.com/Opera/{opera_id}/Staff"

    def _run(self, **kwargs) -> str:
        try:
            # 如果输入是字符串，尝试解析为字典
            if isinstance(kwargs, str):
                import json
                kwargs = json.loads(kwargs)

            action = kwargs.get("action")
            opera_id = kwargs.get("opera_id")
            staff_id = kwargs.get("staff_id")
            name = kwargs.get("name")
            is_on_stage = kwargs.get("is_on_stage")
            data = kwargs.get("data")

            base_url = self._get_base_url(opera_id)

            if action == "get_all":
                result = self._make_request("GET", base_url)
                return f"状态码: {result['status_code']}, 详细内容: {str(result['data'])}"

            elif action == "get":
                if not staff_id:
                    raise ValueError("获取Staff需要提供staff_id")
                result = self._make_request("GET", f"{base_url}/{staff_id}")
                return f"状态码: {result['status_code']}, 详细内容: {str(result['data'])}"

            elif action == "get_by_name":
                if not name:
                    raise ValueError("按名称获取Staff需要提供name")
                params = {"name": name}
                if is_on_stage is not None:
                    params["isOnStage"] = is_on_stage
                result = self._make_request("GET", f"{base_url}/ByName", params=params)
                return f"状态码: {result['status_code']}, 详细内容: {str(result['data'])}"

            elif action == "get_by_name_like":
                if not name:
                    raise ValueError("按名称模糊查询Staff需要提供name")
                params = {"nameLike": name}
                if is_on_stage is not None:
                    params["isOnStage"] = is_on_stage
                result = self._make_request("GET", f"{base_url}/ByNameLike", params=params)
                return f"状态码: {result['status_code']}, 详细内容: {str(result['data'])}"

            elif action == "get_filtered":
                if not data:
                    raise ValueError("过滤查询Staff需要提供filter数据")
                result = self._make_request("POST", f"{base_url}/Get", json=data.model_dump(by_alias=True))
                return f"状态码: {result['status_code']}, 详细内容: {str(result['data'])}"

            elif action == "create":
                if not data:
                    raise ValueError("创建Staff需要提供data")
                result = self._make_request("POST", base_url, json=data.model_dump(by_alias=True))
                return f"状态码: {result['status_code']}, 详细内容: {str(result['data'])}"

            elif action == "update":
                if not staff_id or not data:
                    raise ValueError("更新Staff需要提供staff_id和data")
                # 如果只更新is_on_stage或parameter，使用GET方式更新
                if (len(data.model_dump(exclude_none=True)) == 1 and 
                    (data.is_on_stage is not None or data.parameter is not None)):
                    params = {}
                    if data.is_on_stage is not None:
                        params["isOnStage"] = data.is_on_stage
                    if data.parameter is not None:
                        params["parameter"] = data.parameter
                    result = self._make_request("GET", f"{base_url}/{staff_id}/Update", params=params)
                else:
                    # 否则使用PUT方式更新
                    result = self._make_request(
                        "PUT",
                        f"{base_url}/{staff_id}",
                        json=data.model_dump(by_alias=True)
                    )
                return f"状态码: {result['status_code']}, " + (
                    "Staff更新成功" if result['data'] is None else f"详细内容: {str(result['data'])}")

            elif action == "delete":
                if not staff_id:
                    raise ValueError("删除Staff需要提供staff_id")
                result = self._make_request("DELETE", f"{base_url}/{staff_id}")
                return f"状态码: {result['status_code']}, Staff删除成功"

            else:
                raise ValueError(f"不支持的操作: {action}")

        except Exception as e:
            return f"操作失败: {str(e)}"
