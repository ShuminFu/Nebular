from crewai.tools import BaseTool
from typing import Type, Optional
from uuid import UUID
import httpx
from pydantic import BaseModel, Field
from Opera.FastAPI.models import Bot, BotForCreation, BotForUpdate
import os
import asyncio

class EmptySchema(BaseModel):
    pass

class BaseBotTool(BaseTool):
    base_url: str = "http://opera.nti56.com/Bot"
    
    def _make_request(self, method: str, url: str, json=None) -> dict:
        """同步请求方法"""
        with httpx.Client() as client:
            response = client.request(method, url, json=json)
            response.raise_for_status()
            return response.json() if response.text else None

class GetAllBotsTool(BaseBotTool):
    name: str = "get_all_bots"
    description: str = """获取所有Bot的列表。
    输入: 无需输入参数
    输出: Bot列表，每个Bot包含:
        - id: UUID
        - name: str
        - description: Optional[str]
        - is_active: bool
        - call_shell_on_opera_started: Optional[str]
        - default_tags: Optional[str]
        - default_roles: Optional[str]
        - default_permissions: Optional[str]
    """
    args_schema: Type[BaseModel] = EmptySchema

    def _run(self) -> str:
        result = self._make_request("GET", self.base_url)
        return str(result)

class GetBotByIdInput(BaseModel):
    bot_id: UUID = Field(..., description="Bot的UUID")

class GetBotByIdTool(BaseBotTool):
    name: str = "get_bot_by_id"
    description: str = """通过ID获取特定Bot的信息。
    输入:
        - bot_id: UUID (Bot的唯一标识符)
    输出: 单个Bot的详细信息，包含:
        - id: UUID
        - name: str
        - description: Optional[str]
        - is_active: bool
        - call_shell_on_opera_started: Optional[str]
        - default_tags: Optional[str]
        - default_roles: Optional[str]
        - default_permissions: Optional[str]
    """
    args_schema: Type[BaseModel] = GetBotByIdInput

    def _run(self, bot_id: UUID) -> str:
        result = self._make_request("GET", f"{self.base_url}/{bot_id}")
        return str(result)

class CreateBotTool(BaseBotTool):
    name: str = "create_bot"
    description: str = """创建新的Bot。
    输入可以是JSON字符串或对象，包含以下字段:
    {
        "name": "bot名称",  # 必填，字符串类型
        "description": "bot描述",  # 可选，字符串类型
        "call_shell_on_opera_started": "启动命令",  # 可选，字符串类型
        "default_tags": "默认标签",  # 可选，字符串类型
        "default_roles": "默认角色",  # 可选，字符串类型
        "default_permissions": "默认权限"  # 可选，字符串类型
    }
    
    示例:
    {
        "name": "测试机器人",
        "description": "这是一个测试机器人"
    }
    
    输出: 创建成功的Bot完整信息，包含自动生成的ID和其他字段
    """
    args_schema: Type[BaseModel] = BotForCreation

    def _run(self, **kwargs) -> str:
        try:
            if isinstance(kwargs.get('bot'), str):
                import json
                data = json.loads(kwargs['bot'])
            else:
                data = kwargs
            
            bot = BotForCreation(**data)
            result = self._make_request("POST", self.base_url, json=bot.model_dump())
            return str(result)
        except Exception as e:
            return f"创建Bot失败: {str(e)}"

class UpdateBotInput(BaseModel):
    bot_id: UUID = Field(..., description="Bot的UUID")
    update_data: BotForUpdate = Field(..., description="""更新的Bot数据，必须包含以下字段：
        - description: Optional[str] - 新的描述
        - isDescriptionUpdated: bool - 是否更新描述
        - call_shell_on_opera_started: Optional[str] - 新的启动命令
        - isCallShellOnOperaStartedUpdated: bool - 是否更新启动命令
        - default_tags: Optional[str] - 新的默认标签
        - isDefaultTagsUpdated: bool - 是否更新默认标签
        - default_roles: Optional[str] - 新的默认角色
        - isDefaultRolesUpdated: bool - 是否更新默认角色
        - default_permissions: Optional[str] - 新的默认权限
        - isDefaultPermissionsUpdated: bool - 是否更新默认权限
    """)

class UpdateBotTool(BaseBotTool):
    name: str = "update_bot"
    description: str = """更新现有Bot的信息。
    输入可以是JSON字符串或对象，包含以下字段:
    {
        "bot_id": "uuid-here",
        "name": "更新后的名称",
        "description": "更新后的描述",
        "is_description_updated": true,
        "call_shell_on_opera_started": "新的启动命令",
        "is_call_shell_on_opera_started_updated": true,
        "default_tags": "新的标签",
        "is_default_tags_updated": true,
        "default_roles": "新的角色",
        "is_default_roles_updated": true,
        "default_permissions": "新的权限",
        "is_default_permissions_updated": true
    }

    注意：每个字段的更新都需要设置对应的 is_xxx_updated 标志为 true
    如果不需要更新某个字段，可以将对应的 is_xxx_updated 设为 false

    输出: 更新成功的确认消息
    """
    args_schema: Type[BaseModel] = UpdateBotInput

    def _run(self, bot_id: UUID, update_data: dict) -> str:
        try:
            if isinstance(update_data, str):
                import json
                data = json.loads(update_data)
            else:
                data = update_data
            
            bot_update = BotForUpdate(**data)
            result = self._make_request(
                "PUT", 
                f"{self.base_url}/{bot_id}", 
                json=bot_update.model_dump(by_alias=True)
            )
            return "Bot更新成功" if result is None else str(result)
        except Exception as e:
            return f"更新Bot失败: {str(e)}"

class DeleteBotInput(BaseModel):
    bot_id: UUID = Field(..., description="要删除的Bot的UUID")

class DeleteBotTool(BaseBotTool):
    name: str = "delete_bot"
    description: str = """删除指定的Bot。
    输入:
        - bot_id: UUID (要删除的Bot ID)
    输出: 删除成功的确认消息
    """
    args_schema: Type[BaseModel] = DeleteBotInput

    def _run(self, bot_id: UUID) -> str:
        self._make_request("DELETE", f"{self.base_url}/{bot_id}")
        return "Bot删除成功"