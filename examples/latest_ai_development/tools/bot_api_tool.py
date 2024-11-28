from typing import Type, Optional, Dict, Any, Union
from uuid import UUID
import httpx
from pydantic import BaseModel, Field, field_validator, ValidationError
from Opera.FastAPI.models import Bot, BotForCreation, BotForUpdate
from crewai_tools.tools.base_tool import BaseTool


class BotToolSchema(BaseModel):
    """Bot工具的基础输入模式"""
    action: str = Field(..., description="操作类型: create/get/get_all/update/delete")
    bot_id: Optional[UUID] = Field(None,
                                   description="Bot的UUID，仅用于get/update/delete操作，create/get_all/操作不需要该字段")
    data: Optional[Union[Dict[str, Any], BotForCreation, BotForUpdate]] = Field(
        None,
        description="""Bot的数据，根据action类型使用不同的数据模型:
        - create: 使用BotForCreation模型 {
            name: str,
            description?: str,
            callShellOnOperaStarted?: str,
            defaultTags?: str,
            defaultRoles?: str,
            defaultPermissions?: str
        }
        - update: 使用BotForUpdate模型 {
            name?: str,
            isDescriptionUpdated: bool,
            description?: str,
            isCallShellOnOperaStartedUpdated: bool,
            callShellOnOperaStarted?: str,
            isDefaultTagsUpdated: bool,
            defaultTags?: str,
            isDefaultRolesUpdated: bool,
            defaultRoles?: str,
            isDefaultPermissionsUpdated: bool,
            defaultPermissions?: str
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
                return BotForCreation(**v)
            elif action == 'update':
                return BotForUpdate(**v)
            return v
        except ValidationError as e:
            raise ValueError(f"数据验证失败: {str(e)}")


class BotTool(BaseTool):
    name: str = "Bot Manager"
    description: str = """管理Bot的通用工具，支持创建、查询、更新和删除操作。
    
    示例输入:
    1. 创建Bot: {'action': 'create', 'data': {'name': '新Bot', 'description': '描述'}}
    2. 获取所有Bot: {'action': 'get_all'}
    3. 获取单个Bot: {'action': 'get', 'bot_id': 'uuid'}
    4. 更新Bot: {'action': 'update', 'bot_id': 'uuid', 'data': {'isDescriptionUpdated': True, 'description': '新描述'}}
    5. 删除Bot: {'action': 'delete', 'bot_id': 'uuid'}
    """
    args_schema: Type[BaseModel] = BotToolSchema
    base_url: str = "http://opera.nti56.com/Bot"

    def _make_request(self, method: str, url: str, json=None) -> dict:
        """发送HTTP请求的通用方法"""
        with httpx.Client() as client:
            response = client.request(method, url, json=json)
            response.raise_for_status()
            return response.json() if response.text else None

    def _run(self, **kwargs) -> str:
        try:
            # 如果输入是字符串，尝试解析为字典
            if isinstance(kwargs, str):
                import json
                kwargs = json.loads(kwargs)

            action = kwargs.get("action")
            bot_id = kwargs.get("bot_id")
            data = kwargs.get("data")

            if action == "get_all":
                return str(self._make_request("GET", self.base_url))

            elif action == "get":
                if not bot_id:
                    raise ValueError("获取Bot需要提供bot_id")
                return str(self._make_request("GET", f"{self.base_url}/{bot_id}"))

            elif action == "create":
                if not data:
                    raise ValueError("创建Bot需要提供data")
                return str(self._make_request("POST", self.base_url, json=data.model_dump()))

            elif action == "update":
                if not bot_id or not data:
                    raise ValueError("更新Bot需要提供bot_id和data")
                result = self._make_request(
                    "PUT",
                    f"{self.base_url}/{bot_id}",
                    json=data.model_dump(by_alias=True)
                )
                return "Bot更新成功" if result is None else str(result)

            elif action == "delete":
                if not bot_id:
                    raise ValueError("删除Bot需要提供bot_id")
                self._make_request("DELETE", f"{self.base_url}/{bot_id}")
                return "Bot删除成功"

            else:
                raise ValueError(f"不支持的操作: {action}")

        except Exception as e:
            return f"操作失败: {str(e)}"
