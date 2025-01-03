from fastapi import APIRouter, HTTPException
from typing import List, Optional
from uuid import UUID
from models import Staff, StaffForCreation, StaffForUpdate, StaffForFilter

router = APIRouter(
    prefix="/src/{opera_id}/Staff",
    tags=["Staff"]
)


@router.get("/", response_model=List[Staff])
async def get_all_staff(opera_id: UUID):
    """
    获取所有职员
    
    参数:
        opera_id (UUID): src ID
        
    返回:
        List[Staff]: 职员列表，包含以下属性:
            - id (UUID): 职员ID
            - bot_id (UUID): Bot ID
            - name (str): 职员名称
            - parameter (str): 职员参数
            - is_on_stage (bool): 是否在台上
            - tags (str): 标签
            - roles (str): 角色
            - permissions (str): 权限
            
    错误:
        404: 找不到指定的Opera
    """
    pass


@router.post("/Get", response_model=List[Staff])
async def get_filtered_staff(opera_id: UUID, filter: Optional[StaffForFilter] = None):
    """
    按条件获取职员列表
    
    参数:
        opera_id (UUID): src ID
        filter (StaffForFilter, optional): 过滤条件
            - bot_id (UUID, optional): Bot ID
            - name (str, optional): 精确匹配名称
            - name_like (str, optional): 模糊匹配名称
            - is_on_stage (bool, optional): 是否在台上
    """
    pass


@router.get("/{staff_id}", response_model=Staff)
async def get_staff(opera_id: UUID, staff_id: UUID):
    """
    获取指定职员
    
    参数:
        opera_id (UUID): src ID
        staff_id (UUID): 职员ID
        
    返回:
        Staff: 职员信息，包含以下属性:
            - id (UUID): 职员ID
            - bot_id (UUID): Bot ID
            - name (str): 职员名称
            - parameter (str): 职员参数
            - is_on_stage (bool): 是否在台上
            - tags (str): 标签
            - roles (str): 角色
            - permissions (str): 权限
            
    错误:
        404: 找不到指定的Opera或职员
    """
    pass


@router.put("/{staff_id}", status_code=204)
async def update_staff(opera_id: UUID, staff_id: UUID, staff: StaffForUpdate):
    """
    更新职员信息
    
    参数:
        opera_id (UUID): src ID
        staff_id (UUID): 职员ID
        staff (StaffForUpdate): 职员更新信息
            - is_on_stage (bool, optional): 是否在台上
            - parameter (str, optional): 职员参数
            
    返回:
        204: 更新成功
        
    错误:
        404: 找不到指定的Opera或职员
        400: 更新失败时返回错误信息
    """
    pass


@router.delete("/{staff_id}", status_code=204)
async def delete_staff(opera_id: UUID, staff_id: UUID):
    """
    删除职员
    
    参数:
        opera_id (UUID): src ID
        staff_id (UUID): 职员ID
        
    返回:
        204: 删除成功
        
    错误:
        404: 找不到指定的Opera或职员
        400: 删除失败时返回错误信息
    """
    pass


@router.get("/{staff_id}/Update")
async def update_staff_by_get(
        opera_id: UUID,
        staff_id: UUID,
        is_on_stage: Optional[bool] = None,
        parameter: Optional[str] = None
):
    """
    通过GET方法更新职员信息
    
    参数:
        opera_id (UUID): src ID
        staff_id (UUID): 职员ID
        is_on_stage (bool, optional): 非空则更新OnStage状态
        parameter (str, optional): 非空则更新Parameter参数
        
    返回:
        204: 更新成功
        304: 无需修改
        404: 找不到指定的Opera或职员
    """
    if not opera_id or not staff_id:
        raise HTTPException(status_code=404, detail="Opera或职员不存在")

    # 如果没有需要更新的参数，返回304
    if is_on_stage is None and parameter is None:
        return HTTPException(status_code=304, detail="无需修改")

    # 模拟更新成功
    return None


@router.get("/ByName", response_model=List[Staff])
async def get_staff_by_name(
        opera_id: UUID,
        name: str,
        is_on_stage: Optional[bool] = None
):
    """
    获取指定Name的职员

    参数:
        opera_id (UUID): src ID
        name (str): 职员Name
        is_on_stage (bool, optional): 当指定且为true时，只处理OnStage的职员

    返回:
        List[Staff]: 职员列表
    """
    pass


@router.get("/ByNameLike", response_model=List[Staff])
async def get_staff_by_name_like(
        opera_id: UUID,
        name_like: str,
        is_on_stage: Optional[bool] = None
):
    """
    获取指定Name的职员（模糊匹配）

    参数:
        opera_id (UUID): src ID
        name_like (str): 职员Name以Like方式匹配
        is_on_stage (bool, optional): 当指定且为true时，只处理OnStage的职员

    返回:
        List[Staff]: 职员列表
    """
    pass


@router.post("/", response_model=Staff)
async def create_staff(opera_id: UUID, staff: StaffForCreation):
    """
    创建职员
    
    参数:
        opera_id (UUID): src ID
        staff (StaffForCreation): 职员创建信息
    
    返回:
        Staff: 创建的职员信息
        
    错误:
        404: 找不到指定的Opera
        400: 创建失败时返回错误信息
    """
    pass
