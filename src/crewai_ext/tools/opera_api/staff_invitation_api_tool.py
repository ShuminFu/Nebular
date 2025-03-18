"""Staff邀请管理API工具模块，提供Staff邀请的创建、查询、删除和接受等功能。"""

from typing import Type, Optional, Dict, Any, Union
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, ValidationError
from src.opera_service.api.models import (
    StaffInvitationForCreation,
    StaffInvitationForAcceptance
)
from .base_api_tool import BaseApiTool


class StaffInvitationToolSchema(BaseModel):
    """Staff邀请工具的基础输入模式"""
    action: str = Field(..., description="操作类型: create/get/get_all/delete/accept")
    opera_id: UUID = Field(..., description="Opera的UUID")
    invitation_id: Optional[UUID] = Field(None, description="邀请的UUID，用于get/delete/accept操作")
    data: Optional[Union[Dict[str, Any], StaffInvitationForCreation, StaffInvitationForAcceptance]] = Field(
        None,
        description="""Staff邀请的数据，根据action类型使用不同的数据模型:
        - create: 使用StaffInvitationForCreation模型
        - accept: 使用StaffInvitationForAcceptance模型
        """
    )

    @field_validator('data')
    @classmethod
    def validate_data(cls, v, values):
        if not v:
            return v

        action = values.data.get('action')
        try:
            if action == 'create':
                return StaffInvitationForCreation(**v)
            elif action == 'accept':
                return StaffInvitationForAcceptance(**v)
            return v
        except ValidationError as e:
            raise ValueError(f"数据验证失败: {str(e)}") from e


class StaffInvitationTool(BaseApiTool):
    name: str = "Staff Invitation Manager"
    description: str = """管理Staff邀请的通用工具，支持创建、查询、删除和接受操作。
    
    示例输入:
    1. 创建邀请: {
        'action': 'create',
        'opera_id': 'uuid',
        'data': {
            'bot_id': 'uuid',
            'parameter': '{"key": "value"}',
            'tags': 'tag1,tag2',
            'roles': 'role1,role2',
            'permissions': 'perm1,perm2'
        }
    }
    2. 获取所有邀请: {'action': 'get_all', 'opera_id': 'uuid'}
    3. 获取单个邀请: {'action': 'get', 'opera_id': 'uuid', 'invitation_id': 'uuid'}
    4. 删除邀请: {'action': 'delete', 'opera_id': 'uuid', 'invitation_id': 'uuid'}
    5. 接受邀请: {
        'action': 'accept',
        'opera_id': 'uuid',
        'invitation_id': 'uuid',
        'data': {
            'name': 'staff_name',
            'parameter': '{"key": "value"}',
            'is_on_stage': "True",
            'tags': 'tag1,tag2',
            'roles': 'role1,role2',
            'permissions': 'perm1,perm2'
        }
    }
    """
    args_schema: Type[BaseModel] = StaffInvitationToolSchema

    def _get_base_url(self, opera_id: UUID) -> str:
        """获取基础URL"""
        return f"{self._get_api_base_url()}/Opera/{opera_id}/StaffInvitation"

    def _run(self, *args, **kwargs) -> str:
        try:
            # 如果输入是字符串，尝试解析为字典
            if isinstance(kwargs, str):
                import json
                kwargs = json.loads(kwargs)

            action = kwargs.get("action")
            opera_id = kwargs.get("opera_id")
            invitation_id = kwargs.get("invitation_id")
            data = kwargs.get("data")

            base_url = self._get_base_url(opera_id)

            if action == "get_all":
                result = self._make_request("GET", base_url)
                return f"状态码: {result['status_code']}, 详细内容: {str(result['data'])}"

            elif action == "get":
                if not invitation_id:
                    raise ValueError("获取Staff邀请需要提供invitation_id")
                result = self._make_request("GET", f"{base_url}/{invitation_id}")
                return f"状态码: {result['status_code']}, 详细内容: {str(result['data'])}"

            elif action == "create":
                if not data:
                    raise ValueError("创建Staff邀请需要提供data")
                result = self._make_request("POST", base_url, json=data.model_dump(by_alias=True))
                return f"状态码: {result['status_code']}, 详细内容: {str(result['data'])}"

            elif action == "delete":
                if not invitation_id:
                    raise ValueError("删除Staff邀请需要提供invitation_id")
                result = self._make_request("DELETE", f"{base_url}/{invitation_id}")
                return f"状态码: {result['status_code']}, " + (
                    "Staff邀请删除成功" if result['status_code'] == 204 else f"详细内容: {str(result['data'])}")

            elif action == "accept":
                if not invitation_id or not data:
                    raise ValueError("接受Staff邀请需要提供invitation_id和data")
                result = self._make_request(
                    "POST",
                    f"{base_url}/{invitation_id}/Accept",
                    json=data.model_dump(by_alias=True)
                )
                return f"状态码: {result['status_code']}, 详细内容: {str(result['data'])}"

            else:
                raise ValueError(f"不支持的操作: {action}")

        except Exception as e:
            return f"操作失败: {str(e)}"
