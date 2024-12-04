from pydantic import BaseModel, Field, field_validator, AliasGenerator
from typing import List, Optional, Dict
from datetime import datetime
from uuid import UUID
from enum import IntEnum
import json
from pydantic.alias_generators import to_camel, to_pascal, to_snake


class CamelBaseModel(BaseModel):
    """基础模型类，自动将所有字段转换为大驼峰（序列化时），小驼峰（验证构建时）"""

    class Config:
        alias_generator = AliasGenerator(
            validation_alias=lambda field_name: to_camel(field_name),
            serialization_alias=lambda field_name: to_pascal(field_name),
        )
        populate_by_name = True

    def model_dump(self, **kwargs):
        """重写model_dump方法，确保UUID被正确序列化"""
        def convert_uuid(obj):
            if isinstance(obj, UUID):
                return str(obj)
            elif isinstance(obj, list):
                return [convert_uuid(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: convert_uuid(v) for k, v in obj.items()}
            return obj

        data = super().model_dump(**kwargs)
        return convert_uuid(data)


# 维护状态枚举
class MaintenanceState(IntEnum):
    NORMAL = 0
    CREATING = 1
    DELETING = 2


# Bot相关模型
class Bot(CamelBaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    is_active: bool
    call_shell_on_opera_started: Optional[str] = None
    is_default_tags_updated: Optional[str] = None
    default_roles: Optional[str] = None
    default_permissions: Optional[str] = None


class BotForCreation(CamelBaseModel):
    name: str
    description: Optional[str] = None
    call_shell_on_opera_started: Optional[str] = None
    default_tags: Optional[str] = None
    default_roles: Optional[str] = None
    default_permissions: Optional[str] = None


class BotForUpdate(CamelBaseModel):
    name: Optional[str] = None
    is_description_updated: bool
    description: Optional[str] = None
    is_call_shell_on_opera_started_updated: bool
    call_shell_on_opera_started: Optional[str] = None
    is_default_tags_updated: bool
    default_tags: Optional[str] = None
    is_default_roles_updated: bool
    default_roles: Optional[str] = None
    is_default_permissions_updated: bool
    default_permissions: Optional[str] = None


# Opera相关模型
class OperaBase(CamelBaseModel):
    """Opera基础模型，包含共同的字段"""
    name: str = Field(..., description="Opera名称")
    description: Optional[str] = Field(None, description="Opera描述")

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError('名称不能为空')
        return v.strip()


class OperaForCreation(OperaBase):
    """Opera创建请求模型"""
    parent_id: Optional[UUID] = Field(None, description="父Opera ID")
    database_name: Optional[str] = Field(None, description="数据库名称")

    def model_dump(self, **kwargs):
        """重写model_dump方法，自动生成database_name"""
        data = super().model_dump(**kwargs)
        if not data.get('database_name'):
            # 生成格式: opera_{name}_{timestamp}
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_name = ''.join(c if c.isalnum() else '_' for c in self.name.lower())
            data['database_name'] = f"opera_{safe_name}_{timestamp}"
        return data

    class Config:
        json_schema_extra = {
            "example": {
                "name": "测试Opera",
                "description": "这是一个测试Opera",
                "parent_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }


class OperaForUpdate(CamelBaseModel):
    """Opera更新请求模型"""
    name: Optional[str] = Field(None, description="Opera名称")
    is_description_updated: bool = Field(..., description="是否更新描述")
    description: Optional[str] = Field(None, description="Opera描述")

    @field_validator('name')
    @classmethod
    def name_not_empty_if_present(cls, v):
        if v is not None and not v.strip():
            raise ValueError('如果提供名称，则不能为空')
        return v.strip() if v else v


class Opera(OperaBase):
    """Opera响应模型"""
    id: UUID = Field(..., description="Opera ID")
    parent_id: Optional[UUID] = Field(None, description="父Opera ID")
    database_name: str = Field(..., description="数据库名称")

    class Config:
        from_attributes = True


class OperaWithMaintenanceState(Opera):
    """带维护状态的Opera响应模型"""
    maintenance_state: MaintenanceState = Field(
        MaintenanceState.NORMAL,
        description="维护状态: 0=正常, 1=创建中, 2=删除中"
    )


# Resource相关模型
class Resource(CamelBaseModel):
    id: UUID
    name: str
    description: str
    mime_type: str
    last_update_time: datetime
    last_update_staff_name: str


class ResourceForCreation(CamelBaseModel):
    name: str
    description: str
    mime_type: str
    last_update_staff_name: str
    temp_file_id: UUID


class ResourceForUpdate(CamelBaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    mime_type: Optional[str] = None
    last_update_staff_name: str
    temp_file_id: Optional[UUID] = None


class ResourceForFilter(CamelBaseModel):
    name: Optional[str] = None
    name_like: Optional[str] = None
    mime_type: Optional[str] = None
    mime_type_like: Optional[str] = None
    last_update_time_not_before: Optional[datetime] = None
    last_update_time_not_after: Optional[datetime] = None
    last_update_staff_name: Optional[str] = None
    last_update_staff_name_like: Optional[str] = None


# Dialogue相关模型
class Dialogue(CamelBaseModel):
    index: int
    time: datetime
    stage_index: Optional[int] = None
    staff_id: Optional[UUID] = None
    is_narratage: bool
    is_whisper: bool
    text: str
    tags: Optional[str] = None
    mentioned_staff_ids: Optional[List[UUID]] = None


class DialogueForCreation(CamelBaseModel):
    is_stage_index_null: bool
    staff_id: Optional[UUID] = None
    is_narratage: bool
    is_whisper: bool
    text: str
    tags: Optional[str] = None
    mentioned_staff_ids: Optional[List[UUID]] = None


class DialogueForFilter(CamelBaseModel):
    index_not_before: Optional[int] = None
    index_not_after: Optional[int] = None
    top_limit: Optional[int] = 100
    stage_index: Optional[int] = None
    includes_stage_index_null: bool
    includes_narratage: bool
    includes_for_staff_id_only: Optional[UUID] = None
    includes_staff_id_null: bool


# Staff相关模型
class JsonParameterModel(CamelBaseModel):
    """包含 JSON 参数字段的基础模型"""
    parameter: str = Field(..., description="参数 (JSON格式)")

    @field_validator('parameter')
    @classmethod
    def validate_parameter(cls, v):
        try:
            if v:
                json.loads(v)
            return v
        except json.JSONDecodeError:
            raise ValueError("参数必须是有效的JSON格式")


class OptionalJsonParameterModel(CamelBaseModel):
    """包含可选 JSON 参数字段的基础模型"""
    parameter: Optional[str] = Field(None, description="参数 (JSON格式)")

    @field_validator('parameter')
    @classmethod
    def validate_parameter(cls, v):
        try:
            if v:
                json.loads(v)
            return v
        except json.JSONDecodeError:
            raise ValueError("参数必须是有效的JSON格式")


class Staff(JsonParameterModel, CamelBaseModel):
    id: UUID
    bot_id: UUID
    name: str
    is_on_stage: bool
    tags: str
    roles: str
    permissions: str


class StaffForCreation(JsonParameterModel, CamelBaseModel):
    bot_id: UUID
    name: str
    is_on_stage: bool
    tags: str
    roles: str
    permissions: str


class StaffForUpdate(OptionalJsonParameterModel, CamelBaseModel):
    is_on_stage: Optional[bool] = None


class StaffForFilter(CamelBaseModel):
    """Staff筛选条件模型"""
    bot_id: Optional[UUID] = Field(None, description="Bot ID")
    name: Optional[str] = Field(None, description="Staff名称（精确匹配）")
    name_like: Optional[str] = Field(None, description="Staff名称（模糊匹配）")
    is_on_stage: Optional[bool] = Field(None, description="是否在舞台上")

    class Config:
        json_schema_extra = {
            "example": {
                "botId": "122e4567-e89b-12d3-a456-426614174000",
                "name": "StaffName",
                "nameLike": "Staff",
                "isOnStage": True
            }
        }


# StaffInvitation相关模型
class StaffInvitation(JsonParameterModel, CamelBaseModel):
    id: UUID
    bot_id: UUID
    tags: str
    roles: str
    permissions: str


class StaffInvitationForCreation(JsonParameterModel, CamelBaseModel):
    bot_id: UUID
    tags: str
    roles: str
    permissions: str


class StaffInvitationForAcceptance(OptionalJsonParameterModel, CamelBaseModel):
    name: str
    is_on_stage: bool
    tags: Optional[str] = None
    roles: Optional[str] = None
    permissions: Optional[str] = None


# Stage相关模型
class Stage(CamelBaseModel):
    index: int
    name: str


class StageForCreation(CamelBaseModel):
    name: str


# TempFile相关模型
class TempFile(CamelBaseModel):
    id: UUID
    length: int


# Property相关模型
class OperaProperty(CamelBaseModel):
    properties: Dict[str, str]


class OperaPropertyForUpdate(CamelBaseModel):
    properties: Optional[Dict[str, str]] = None
    properties_to_remove: Optional[List[str]] = None
