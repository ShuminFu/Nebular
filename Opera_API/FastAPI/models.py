from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict
from datetime import datetime
from uuid import UUID
from enum import IntEnum

# 维护状态枚举
class MaintenanceState(IntEnum):
    NORMAL = 0
    CREATING = 1
    DELETING = 2

# Bot相关模型
class Bot(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    is_active: bool
    call_shell_on_opera_started: Optional[str] = None
    is_default_tags_updated: Optional[str] = None
    default_roles: Optional[str] = None
    default_permissions: Optional[str] = None

class BotForCreation(BaseModel):
    name: str
    description: Optional[str] = None
    call_shell_on_opera_started: Optional[str] = None
    default_tags: Optional[str] = None
    default_roles: Optional[str] = None
    default_permissions: Optional[str] = None

class BotForUpdate(BaseModel):
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
class OperaBase(BaseModel):
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
    database_name: str = Field(..., description="数据库名称")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "测试Opera",
                "description": "这是一个测试Opera",
                "parent_id": "123e4567-e89b-12d3-a456-426614174000",
                "database_name": "test_db"
            }
        }

class OperaForUpdate(BaseModel):
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

# Staff相关模型
class Staff(BaseModel):
    id: UUID
    bot_id: UUID
    name: str
    parameter: str
    is_on_stage: bool
    tags: str
    roles: str
    permissions: str

class StaffForCreation(BaseModel):
    bot_id: UUID
    name: str
    parameter: str
    is_on_stage: bool
    tags: str
    roles: str
    permissions: str

class StaffForUpdate(BaseModel):
    is_on_stage: Optional[bool] = None
    parameter: Optional[str] = None

class StaffForFilter(BaseModel):
    bot_id: Optional[UUID] = None
    name: Optional[str] = None
    name_like: Optional[str] = None
    is_on_stage: Optional[bool] = None

# Resource相关模型
class Resource(BaseModel):
    id: UUID
    name: str
    description: str
    mime_type: str
    last_update_time: datetime
    last_update_staff_name: str

class ResourceForCreation(BaseModel):
    name: str
    description: str
    mime_type: str
    last_update_staff_name: str
    temp_file_id: UUID

class ResourceForUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    mime_type: Optional[str] = None
    last_update_staff_name: str
    temp_file_id: Optional[UUID] = None

class ResourceForFilter(BaseModel):
    name: Optional[str] = None
    name_like: Optional[str] = None
    mime_type: Optional[str] = None
    mime_type_like: Optional[str] = None
    last_update_time_not_before: Optional[datetime] = None
    last_update_time_not_after: Optional[datetime] = None
    last_update_staff_name: Optional[str] = None
    last_update_staff_name_like: Optional[str] = None

# Dialogue相关模型
class Dialogue(BaseModel):
    index: int
    time: datetime
    stage_index: Optional[int] = None
    staff_id: Optional[UUID] = None
    is_narratage: bool
    is_whisper: bool
    text: str
    tags: Optional[str] = None
    mentioned_staff_ids: Optional[List[UUID]] = None

class DialogueForCreation(BaseModel):
    is_stage_index_null: bool
    staff_id: Optional[UUID] = None
    is_narratage: bool
    is_whisper: bool
    text: str
    tags: Optional[str] = None
    mentioned_staff_ids: Optional[List[UUID]] = None

class DialogueForFilter(BaseModel):
    index_not_before: Optional[int] = None
    index_not_after: Optional[int] = None
    top_limit: Optional[int] = 100
    stage_index: Optional[int] = None
    includes_stage_index_null: bool
    includes_narratage: bool
    includes_for_staff_id_only: Optional[UUID] = None
    includes_staff_id_null: bool

# StaffInvitation相关模型
class StaffInvitation(BaseModel):
    id: UUID
    bot_id: UUID
    parameter: str
    tags: str
    roles: str
    permissions: str

class StaffInvitationForCreation(BaseModel):
    bot_id: UUID
    parameter: str
    tags: str
    roles: str
    permissions: str

class StaffInvitationForAcceptance(BaseModel):
    name: str
    parameter: Optional[str] = None
    is_on_stage: bool
    tags: Optional[str] = None
    roles: Optional[str] = None
    permissions: Optional[str] = None

# Stage相关模型
class Stage(BaseModel):
    index: int
    name: str

class StageForCreation(BaseModel):
    name: str

# TempFile相关模型
class TempFile(BaseModel):
    id: UUID
    length: int

# Property相关模型
class OperaProperty(BaseModel):
    properties: Dict[str, str]

class OperaPropertyForUpdate(BaseModel):
    properties: Optional[Dict[str, str]] = None
    properties_to_remove: Optional[List[str]] = None 