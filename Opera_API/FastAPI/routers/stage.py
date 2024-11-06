from fastapi import APIRouter, HTTPException
from typing import List, Optional
from uuid import UUID
from models import Stage, StageForCreation

router = APIRouter(
    prefix="/Opera/{opera_id}/Stage",
    tags=["Stage"]
)

@router.get("/", response_model=List[Stage])
async def get_all_stages(opera_id: UUID):
    """
    获取所有场幕
    
    参数:
        opera_id (UUID): Opera ID
        
    返回:
        List[Stage]: 场幕列表，每个场幕包含:
            - index (int): 场幕索引
            - name (str): 场幕名称
            
    错误:
        404: 找不到指定的Opera
    """
    pass

@router.get("/-1", response_model=Stage)
@router.get("/Current", response_model=Stage)
async def get_current_stage(opera_id: UUID, force: Optional[bool] = None):
    """
    获取当前场幕信息
    
    参数:
        opera_id (UUID): Opera ID
        force (bool, optional): 当指定且为true时，强制穿透缓存，从数据库读取
        
    返回:
        Stage: 当前场幕信息
            - index (int): 场幕索引
            - name (str): 场幕名称
            
    错误:
        204: 当前没有场幕
        404: 找不到指定的Opera
    """
    pass

@router.get("/{stage_index}", response_model=Stage)
async def get_stage(opera_id: UUID, stage_index: int):
    """
    获取指定场幕
    
    参数:
        opera_id (UUID): Opera ID
        stage_index (int): 场幕索引
        
    返回:
        Stage: 场幕信息
            - index (int): 场幕索引
            - name (str): 场幕名称
            
    错误:
        404: 找不到指定的Opera或场幕
    """
    pass

@router.post("/", response_model=Stage)
async def create_stage(opera_id: UUID, stage: StageForCreation):
    """
    创建场幕
    
    参数:
        opera_id (UUID): Opera ID
        stage (StageForCreation): 场幕创建信息
            - name (str): 场幕名称
            
    返回:
        Stage: 创建的场幕信息
            - index (int): 场幕索引
            - name (str): 场幕名称
            
    错误:
        404: 找不到指定的Opera
        400: 创建失败时返回错误信息
    """
    pass