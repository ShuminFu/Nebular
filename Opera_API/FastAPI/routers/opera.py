from fastapi import APIRouter, HTTPException
from typing import List, Optional
from uuid import UUID
from models import Opera, OperaWithMaintenanceState, OperaForCreation, OperaForUpdate

router = APIRouter(
    prefix="/Opera",
    tags=["Opera"]
)

@router.get("/", response_model=List[OperaWithMaintenanceState])
async def get_all_operas(parent_id: Optional[UUID] = None):
    """
    获取所有Opera
    
    参数:
        parent_id (UUID, optional): 父Opera ID。不指定时，返回以根为父节点的Opera
        
    返回:
        List[OperaWithMaintenanceState]: Opera列表，每个Opera包含:
            - id (UUID): Opera ID
            - parent_id (UUID, optional): 父Opera ID
            - name (str): Opera名称
            - description (str, optional): Opera描述
            - database_name (str): 数据库名称
            - maintenance_state (int): 维护状态
                - 0: 正常
                - 1: 创建中
                - 2: 删除中
    """
    pass

@router.get("/{opera_id}", response_model=OperaWithMaintenanceState)
async def get_opera(opera_id: UUID):
    """
    获取指定Opera
    
    参数:
        opera_id (UUID): Opera ID
        
    返回:
        OperaWithMaintenanceState: Opera信息
        
    错误:
        404: 找不到指定的Opera
    """
    pass

@router.post("/", response_model=Opera)
async def create_opera(opera: OperaForCreation):
    """
    创建Opera
    
    参数:
        opera (OperaForCreation): Opera创建信息
            - parent_id (UUID, optional): 父Opera ID
            - name (str): Opera名称
            - description (str, optional): Opera描述
            - database_name (str): 数据库名称
            
    返回:
        Opera: 创建的Opera信息，包含:
            - id (UUID): Opera ID
            - parent_id (UUID, optional): 父Opera ID
            - name (str): Opera名称
            - description (str, optional): Opera描述
            - database_name (str): 数据库名称
            
    错误:
        400: 创建失败时返回错误信息
    """
    pass

@router.put("/{opera_id}", status_code=204)
async def update_opera(opera_id: UUID, opera: OperaForUpdate):
    """
    更新Opera信息
    
    参数:
        opera_id (UUID): Opera ID
        opera (OperaForUpdate): Opera更新信息
            - name (str, optional): Opera名称
            - is_description_updated (bool): 是否更新描述
            - description (str, optional): Opera描述
            
    返回:
        204: 更新成功
        
    错误:
        404: 找不到指定的Opera
        400: 更新失败时返回错误信息
        
    注意:
        is_description_updated为false时，description会被忽略
    """
    pass

@router.delete("/{opera_id}", status_code=204)
async def delete_opera(opera_id: UUID):
    """
    删除Opera
    
    参数:
        opera_id (UUID): Opera ID
        
    返回:
        204: 删除成功
        
    错误:
        404: 找不到指定的Opera
        400: 删除失败时返回错误信息
    """
    pass