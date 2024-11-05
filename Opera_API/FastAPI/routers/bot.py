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
    获取所有Bot
    
    返回:
        List[Bot]: Bot列表，每个Bot包含:
            - id (UUID): Bot ID
            - name (str): Bot名称
            - description (str, optional): Bot描述
            - is_active (bool): 是否活跃
            - call_shell_on_opera_started (str, optional): Opera启动时调用的shell命令
            - default_tags (str, optional): 默认标签
            - default_roles (str, optional): 默认角色
            - default_permissions (str, optional): 默认权限
    """
    pass

@router.get("/{bot_id}", response_model=Bot)
async def get_bot(bot_id: UUID):
    """
    获取指定Bot
    
    参数:
        bot_id (UUID): Bot ID
        
    返回:
        Bot: Bot信息
        
    错误:
        404: 找不到指定的Bot
    """
    pass

@router.post("/", response_model=Bot)
async def create_bot(bot: BotForCreation):
    """
    创建Bot
    
    参数:
        bot (BotForCreation): Bot创建信息
            - name (str): Bot名称
            - description (str, optional): Bot描述
            - call_shell_on_opera_started (str, optional): Opera启动时调用的shell命令
            - default_tags (str, optional): 默认标签
            - default_roles (str, optional): 默认角色
            - default_permissions (str, optional): 默认权限
            
    返回:
        Bot: 创建的Bot信息
        
    错误:
        400: 创建失败时返回错误信息
    """
    pass

@router.put("/{bot_id}", status_code=204)
async def update_bot(bot_id: UUID, bot: BotForUpdate):
    """
    更新Bot信息
    
    参数:
        bot_id (UUID): Bot ID
        bot (BotForUpdate): Bot更新信息
            - name (str, optional): Bot名称
            - is_description_updated (bool): 是否更新描述
            - description (str, optional): Bot描述
            - is_call_shell_on_opera_started_updated (bool): 是否更新启动命令
            - call_shell_on_opera_started (str, optional): Opera启动时调用的shell命令
            - is_default_tags_updated (bool): 是否更新默认标签
            - default_tags (str, optional): 默认标签
            - is_default_roles_updated (bool): 是否更新默认角色
            - default_roles (str, optional): 默认角色
            - is_default_permissions_updated (bool): 是否更新默认权限
            - default_permissions (str, optional): 默认权限
            
    返回:
        204: 更新成功
        
    错误:
        404: 找不到指定的Bot
        400: 更新失败时返回错误信息
        
    注意:
        各个is_*_updated为false时，对应的值会被忽略
    """
    pass

@router.delete("/{bot_id}", status_code=204)
async def delete_bot(bot_id: UUID):
    """
    删除Bot
    
    参数:
        bot_id (UUID): Bot ID
        
    返回:
        204: 删除成功
        
    错误:
        404: 找不到指定的Bot
        400: 删除失败时返回错误信息
    """
    pass