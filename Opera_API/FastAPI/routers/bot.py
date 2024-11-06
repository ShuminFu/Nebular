from fastapi import APIRouter, HTTPException
from typing import List, Optional
from uuid import UUID
from models import Bot, BotForCreation, BotForUpdate

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