from fastapi import FastAPI, HTTPException, Query, Body, Path
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from enum import IntEnum

app = FastAPI(title="Opera API", version="1.0.0")


# 数据模型定义
class MaintenanceState(IntEnum):
    NORMAL = 0
    CREATING = 1
    DELETING = 2


class Bot(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    is_active: bool
    call_shell_on_opera_started: Optional[str] = None
    default_tag: Optional[str] = None
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


class OperaWithMaintenanceState(BaseModel):
    id: UUID
    parent_id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    database_name: str
    maintenance_state: MaintenanceState


# API路由定义
@app.get("/Bot", response_model=List[Bot], tags=["Bot"])
async def get_all_bots():
    """
    获取所有Bot列表

    返回:
        List[Bot]: Bot列表，包含以下信息:
        - id: Bot唯一标识
        - name: Bot名称
        - description: Bot描述(可选)
        - is_active: 只读属性，表示此Bot是否存在到Opera的SignalR连接
        - call_shell_on_opera_started: Opera启动时调用的shell命令(可选)
        - default_tag: 默认标签(可选)
        - default_roles: 默认角色(可选)
        - default_permissions: 默认权限(可选)
    """
    pass


@app.get("/Bot/{bot_id}", response_model=Bot, tags=["Bot"])
async def get_bot(bot_id: UUID):
    """返回指定Bot"""
    pass


@app.post("/Bot", response_model=Bot, tags=["Bot"])
async def create_bot(bot: BotForCreation):
    """
    创建新的Bot

    参数:
        bot (BotForCreation): Bot创建信息
            - name: Bot名称
            - description: Bot描述(可选)
            - call_shell_on_opera_started: Opera启动时调用的shell命令(可选)
            - default_tags: 默认标签(可选)
            - default_roles: 默认角色(可选)
            - default_permissions: 默认权限(可选)

    返回:
        Bot: 创建成功的Bot完整信息

    错误:
        400: 创建失败时返回错误信息
    """
    pass


@app.put("/Bot/{bot_id}", status_code=204, tags=["Bot"])
async def update_bot(bot_id: UUID, bot: BotForUpdate):
    """更新Bot信息"""
    pass


@app.delete("/Bot/{bot_id}", status_code=204, tags=["Bot"])
async def delete_bot(bot_id: UUID):
    """删除Bot"""
    pass


# Opera相关模型
class OperaForCreation(BaseModel):
    parent_id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    database_name: str


class OperaForUpdate(BaseModel):
    name: Optional[str] = None
    is_description_updated: bool
    description: Optional[str] = None


# Opera API路由
@app.get("/Opera", response_model=List[OperaWithMaintenanceState], tags=["Opera"])
async def get_all_operas(parent_id: Optional[UUID] = None):
    """
    获取所有Opera列表

    参数:
        parent_id (UUID, optional): 父Opera ID。不指定时返回根节点下的Opera

    返回:
        List[OperaWithMaintenanceState]: Opera列表，包含以下信息:
        - id: Opera唯一标识
        - parent_id: 父Opera ID(可选)
        - name: Opera名称
        - description: Opera描述(可选)
        - database_name: 数据库名称
        - maintenance_state: 维护状态
            - 0: 状态正常
            - 1: 正在创建
            - 2: 正在删除
    """
    pass


@app.get("/Opera/{opera_id}", response_model=OperaWithMaintenanceState, tags=["Opera"])
async def get_opera(opera_id: UUID):
    """获取指定Opera"""
    pass


@app.post("/Opera", response_model=OperaWithMaintenanceState, tags=["Opera"])
async def create_opera(opera: OperaForCreation):
    """创建Opera"""
    pass


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


# Staff API路由
@app.get("/Opera/{opera_id}/Staff", response_model=List[Staff], tags=["Staff"])
async def get_all_staff(opera_id: UUID):
    """获取所有职员"""
    pass


@app.post("/Opera/{opera_id}/Staff/Get", response_model=List[Staff], tags=["Staff"])
async def get_filtered_staff(opera_id: UUID, filter: Optional[StaffForFilter] = None):
    """按条件获取职员"""
    pass


@app.get("/Opera/{opera_id}/Staff/ByName", response_model=List[Staff], tags=["Staff"])
async def get_staff_by_name(
        opera_id: UUID,
        name: str,
        is_on_stage: Optional[bool] = None
):
    """获取指定Name的职员"""
    pass


@app.get("/Opera/{opera_id}/Staff/{staff_id}", response_model=Staff, tags=["Staff"])
async def get_staff(opera_id: UUID, staff_id: UUID):
    """获取指定职员"""
    pass


@app.post("/Opera/{opera_id}/Staff", response_model=Staff, tags=["Staff"])
async def create_staff(opera_id: UUID, staff: StaffForCreation):
    """创建职员"""
    pass


@app.put("/Opera/{opera_id}/Staff/{staff_id}", status_code=204, tags=["Staff"])
async def update_staff(opera_id: UUID, staff_id: UUID, staff: StaffForUpdate):
    """更新职员信息"""
    pass


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


# Resource API路由
@app.get("/Opera/{opera_id}/Resource", response_model=List[Resource], tags=["Resource"])
async def get_all_resources(opera_id: UUID):
    """获取所有资源文件"""
    pass


@app.post("/Opera/{opera_id}/Resource/Get", response_model=List[Resource], tags=["Resource"])
async def get_filtered_resources(opera_id: UUID, filter: Optional[ResourceForFilter] = None):
    """按条件获取资源文件"""
    pass


@app.get("/Opera/{opera_id}/Resource/{resource_id}", response_model=Resource, tags=["Resource"])
async def get_resource(opera_id: UUID, resource_id: UUID):
    """获取指定资源文件"""
    pass


@app.post("/Opera/{opera_id}/Resource", response_model=Resource, tags=["Resource"])
async def create_resource(opera_id: UUID, resource: ResourceForCreation):
    """
    创建资源文件

    注意: 创建资源文件前，应先将文件上传为临时文件

    参数:
        opera_id (UUID): Opera ID
        resource (ResourceForCreation): 资源创建信息
            - name: 资源名称
            - description: 资源描述
            - mime_type: MIME类型
            - last_update_staff_name: 最后更新者名称
            - temp_file_id: 临时文件ID

    返回:
        Resource: 创建的资源信息，包含:
            - id: 资源ID
            - name: 资源名称
            - description: 资源描述
            - mime_type: MIME类型
            - last_update_time: 最后更新时间
            - last_update_staff_name: 最后更新者名称

    错误:
        404: 指定的Opera不存在
        400: 创建失败时返回错误信息
    """
    pass


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


# Dialogue API路由
@app.get("/Opera/{opera_id}/Dialogue", response_model=List[Dialogue], tags=["Dialogue"])
async def get_all_dialogues(opera_id: UUID):
    """获取所有对话"""
    pass


@app.post("/Opera/{opera_id}/Dialogue/Get", response_model=List[Dialogue], tags=["Dialogue"])
async def get_filtered_dialogues(opera_id: UUID, filter: Optional[DialogueForFilter] = None):
    """按条件获取对话"""
    pass


@app.get("/Opera/{opera_id}/Dialogue/{dialogue_index}", response_model=Dialogue, tags=["Dialogue"])
async def get_dialogue(opera_id: UUID, dialogue_index: int):
    """获取指定对话"""
    pass


@app.post("/Opera/{opera_id}/Dialogue", response_model=Dialogue, tags=["Dialogue"])
async def create_dialogue(opera_id: UUID, dialogue: DialogueForCreation):
    """创建对话"""
    pass


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


# StaffInvitation API路由
@app.get("/Opera/{opera_id}/StaffInvitation", response_model=List[StaffInvitation], tags=["StaffInvitation"])
async def get_all_staff_invitations(opera_id: UUID):
    """获取所有职员邀请"""
    pass


@app.get("/Opera/{opera_id}/StaffInvitation/{invitation_id}", response_model=StaffInvitation, tags=["StaffInvitation"])
async def get_staff_invitation(opera_id: UUID, invitation_id: UUID):
    """获取指定职员邀请"""
    pass


@app.post("/Opera/{opera_id}/StaffInvitation", response_model=StaffInvitation, tags=["StaffInvitation"])
async def create_staff_invitation(opera_id: UUID, invitation: StaffInvitationForCreation):
    """创建职员邀请"""
    pass


@app.delete("/Opera/{opera_id}/StaffInvitation/{invitation_id}", status_code=204, tags=["StaffInvitation"])
async def delete_staff_invitation(opera_id: UUID, invitation_id: UUID):
    """删除职员邀请"""
    pass


@app.post("/Opera/{opera_id}/StaffInvitation/{invitation_id}/Accept", response_model=UUID, tags=["StaffInvitation"])
async def accept_staff_invitation(opera_id: UUID, invitation_id: UUID, acceptance: StaffInvitationForAcceptance):
    """接受职员邀请"""
    pass


# Stage相关模型
class Stage(BaseModel):
    index: int
    name: str


class StageForCreation(BaseModel):
    name: str


# Stage API路由
@app.get("/Opera/{opera_id}/Stage", response_model=List[Stage], tags=["Stage"])
async def get_all_stages(opera_id: UUID):
    """获取所有场幕"""
    pass


@app.get("/Opera/{opera_id}/Stage/Current", response_model=Stage, tags=["Stage"])
async def get_current_stage(opera_id: UUID, force: Optional[bool] = None):
    """获取当前场幕"""
    pass


@app.get("/Opera/{opera_id}/Stage/{stage_index}", response_model=Stage, tags=["Stage"])
async def get_stage(opera_id: UUID, stage_index: int):
    """获取指定场幕"""
    pass


@app.post("/Opera/{opera_id}/Stage", response_model=Stage, tags=["Stage"])
async def create_stage(opera_id: UUID, stage: StageForCreation):
    """创建场幕"""
    pass


# TempFile相关模型
class TempFile(BaseModel):
    id: UUID
    length: int


# TempFile API路由
@app.post("/TempFile", response_model=TempFile, tags=["TempFile"])
async def upload_temp_file(id: Optional[UUID] = None, file: bytes = Body(...)):
    """
    上传临时文件

    注意:
    1. 临时文件目录在每次Opera启动时将被清空
    2. 当临时文件被作为资源文件使用时，会被移出临时文件目录

    参数:
        id (UUID, optional): 临时文件ID。指定时附加数据到已存在的临时文件，不指定时创建新文件
        file (bytes): 文件数据块(chunk)

    返回:
        TempFile: 临时文件信息
            - id: 临时文件ID
            - length: 当前文件总长度

    错误:
        404: 指定的临时文件不存在
        400: 上传失败时返回错误信息
    """
    pass


@app.post("/TempFile/{temp_file_id}", response_model=TempFile, tags=["TempFile"])
async def append_temp_file(temp_file_id: UUID, file: bytes = Body(...)):
    """附加临时文件"""
    pass


@app.delete("/TempFile/{temp_file_id}", status_code=204, tags=["TempFile"])
async def delete_temp_file(temp_file_id: UUID):
    """删除临时文件"""
    pass


# Property相关模型
class OperaProperty(BaseModel):
    properties: dict[str, str]


class OperaPropertyForUpdate(BaseModel):
    properties: Optional[dict[str, str]] = None
    properties_to_remove: Optional[List[str]] = None


# Property API路由
@app.get("/Opera/{opera_id}/Property", response_model=OperaProperty, tags=["Property"])
async def get_all_properties(opera_id: UUID, force: Optional[bool] = None):
    """获取所有属性"""
    pass


@app.get("/Opera/{opera_id}/Property/ByKey", response_model=str, tags=["Property"])
async def get_property_by_key(opera_id: UUID, key: str, force: Optional[bool] = None):
    """获取指定的属性"""
    pass


@app.put("/Opera/{opera_id}/Property", status_code=204, tags=["Property"])
async def update_properties(opera_id: UUID, property: OperaPropertyForUpdate):
    """更新属性"""
    pass

# 更多API路由和模型定义...