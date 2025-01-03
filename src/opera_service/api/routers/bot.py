from fastapi import APIRouter, Query
from typing import List, Optional
from uuid import UUID
from models import Bot, BotForCreation, BotForUpdate, StaffsOfOpera

router = APIRouter(
    prefix="/Bot",
    tags=["Bot"]
)

@router.get("/", response_model=List[Bot])
async def get_all_bots():
    """
    获取所有Bot。

    返回Bot列表，每个Bot包含：id、name、description、is_active、call_shell_on_opera_started、default_tags、default_roles、default_permissions等信息。
    """
    pass

@router.get("/{bot_id}", response_model=Bot)
async def get_bot(bot_id: UUID):
    """
    获取指定Bot。

    Args:
        bot_id: Bot ID

    Returns:
        返回指定Bot的详细信息

    Raises:
        404: 找不到指定的Bot
    """
    pass

@router.post("/", response_model=Bot)
async def create_bot(bot: BotForCreation):
    """
    创建Bot。

    Args:
        bot: Bot创建信息，包含name、description、call_shell_on_opera_started、default_tags、default_roles、default_permissions等字段

    Returns:
        返回创建的Bot信息

    Raises:
        400: 创建失败时返回错误信息
    """
    pass

@router.put("/{bot_id}", status_code=204)
async def update_bot(bot_id: UUID, bot: BotForUpdate):
    """
    更新Bot信息。

    Args:
        bot_id: Bot ID
        bot: Bot更新信息，包含name、description等字段。各个is_*_updated为false时，对应的值会被忽略

    Returns:
        204: 更新成功

    Raises:
        404: 找不到指定的Bot
        400: 更新失败时返回错误信息
    """
    pass

@router.delete("/{bot_id}", status_code=204)
async def delete_bot(bot_id: UUID):
    """
    删除Bot。

    Args:
        bot_id: Bot ID

    Returns:
        204: 删除成功

    Raises:
        404: 找不到指定的Bot
        400: 删除失败时返回错误信息
    """
    pass

@router.get("/{bot_id}/GetAllStaffs", response_model=List[StaffsOfOpera])
async def get_all_staffs(
    bot_id: UUID,
    need_opera_info: Optional[bool] = Query(False, description="是否包含Opera Name与Description"),
    need_staffs: Optional[int] = Query(1, description="包含Staff的数据内容（0不包含，1只包含Id，2包含Id与Parameter，3包含所有字段）", ge=0, le=3),
    need_staff_invitations: Optional[int] = Query(1, description="包含StaffInvitation的数据内容（0不包含，1只包含Id，2包含Id与Parameter，3包含所有字段）", ge=0, le=3)
):
    """
    获得Bot在所有Opera（缓存中记录）的Staff与StaffInvitation。
    此方法不会导致对应的Opera被缓存，也不会读取对应的缓存数据。

    Args:
        bot_id: Bot ID
        need_opera_info: 是否包含Opera Name与Description，默认false
        need_staffs: 包含Staff的数据内容（0不包含，1只包含Id，2包含Id与Parameter，3包含所有字段），默认1
        need_staff_invitations: 包含StaffInvitation的数据内容（同Staff），默认1

    Returns:
        返回StaffsOfOpera列表，每个StaffsOfOpera包含Opera信息和相关的Staff、StaffInvitation信息

    Raises:
        404: 找不到指定的Bot
        400: 如果need_staffs与need_staff_invitations均为0，或其他错误情况
    """
    if need_staffs == 0 and need_staff_invitations == 0:
        return []
    pass