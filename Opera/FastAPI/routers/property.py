from fastapi import APIRouter, HTTPException
from typing import Optional
from uuid import UUID
from models import OperaProperty, OperaPropertyForUpdate

router = APIRouter(
    prefix="/Opera/{opera_id}/Property",
    tags=["Property"]
)

@router.get("/", response_model=OperaProperty)
async def get_all_properties(opera_id: UUID, force: Optional[bool] = None):
    """
    获取所有属性
    
    参数:
        opera_id (UUID): Opera ID
        force (bool, optional): 当指定且为true时，强制穿透缓存，从数据库读取
        
    返回:
        OperaProperty: 包含所有属性的字典
            - properties (Dict[str, str]): 属性键值对字典
            
    错误:
        404: 找不到指定的Opera
    """
    pass

@router.get("/ByKey", response_model=str)
async def get_property_by_key(opera_id: UUID, key: str, force: Optional[bool] = None):
    """获取指定的属性"""
    pass

@router.put("/", status_code=204)
async def update_properties(opera_id: UUID, property: OperaPropertyForUpdate):
    """
    更新属性
    
    参数:
        opera_id (UUID): Opera ID
        property (OperaPropertyForUpdate): 属性更新信息
            - properties (Dict[str, str], optional): 要更新或新增的属性键值对
            - properties_to_remove (List[str], optional): 要删除的属性键列表
            
    返回:
        204: 更新成功
        
    错误:
        404: 找不到指定的Opera
        400: 更新失败时返回错误信息
        
    注意:
        properties中的键值会覆盖或新增对应的属性
        properties_to_remove中的键会删除对应的属性
    """
    pass