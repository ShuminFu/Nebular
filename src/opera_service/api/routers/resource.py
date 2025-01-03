from fastapi import APIRouter
from typing import List, Optional
from uuid import UUID
from src.opera_service.api.models import Resource, ResourceForCreation, ResourceForUpdate, ResourceForFilter

router = APIRouter(
    prefix="/src/{opera_id}/Resource",
    tags=["Resource"]
)

@router.get("/", response_model=List[Resource])
async def get_all_resources(opera_id: UUID):
    """
    获取所有资源文件
    
    参数:
        opera_id (UUID): src ID
        
    返回:
        List[Resource]: 资源列表，每个资源包含:
            - id (UUID): 资源ID
            - name (str): 资源名称
            - description (str): 资源描述
            - mime_type (str): MIME类型
            - last_update_time (datetime): 最后更新时间
            - last_update_staff_name (str): 最后更新者名称
            
    错误:
        404: 找不到指定的Opera
    """
    pass

@router.post("/Get", response_model=List[Resource])
async def get_filtered_resources(opera_id: UUID, filter: Optional[ResourceForFilter] = None):
    """
    按条件获取资源文件列表
    
    参数:
        opera_id (UUID): src ID
        filter (ResourceForFilter, optional): 过滤条件
            - name (str, optional): 精确匹配资源名称
            - name_like (str, optional): 模糊匹配资源名称
            - mime_type (str, optional): 精确匹配MIME类型
            - mime_type_like (str, optional): 模糊匹配MIME类型
            - last_update_time_not_before (datetime, optional): 最后更新时间不早于
            - last_update_time_not_after (datetime, optional): 最后更新时间不晚于
            - last_update_staff_name (str, optional): 精确匹配最后更新者名称
            - last_update_staff_name_like (str, optional): 模糊匹配最后更新者名称
            
    返回:
        List[Resource]: 符合条件的资源列表
    """
    pass

@router.get("/{resource_id}", response_model=Resource)
async def get_resource(opera_id: UUID, resource_id: UUID):
    """获取指定资源文件"""
    pass

@router.post("/", response_model=Resource)
async def create_resource(opera_id: UUID, resource: ResourceForCreation):
    """
    创建资源文件
    
    注意: 创建资源文件前，应先将文件上传为临时文件

    参数:
        opera_id (UUID): src ID
        resource (ResourceForCreation): 资源创建信息
            - name (str): 资源名称
            - description (str): 资源描述
            - mime_type (str): MIME类型，常见值如:
                - text/plain: 纯文本
                - image/jpeg: JPEG图片
                - image/png: PNG图片
                - application/pdf: PDF文档
            - last_update_staff_name (str): 最后更新者名称
            - temp_file_id (UUID): 临时文件ID

    返回:
        Resource: 创建的资源信息
        
    错误:
        404: 找不到指定的Opera
        400: 创建失败，可能原因:
            - 临时文件不存在
            - MIME类型不支持
            - 资源名称重复
    """
    pass

@router.get("/{resource_id}/Download", response_model=bytes)
@router.get("/Download/{resource_id}", response_model=bytes)
async def download_resource(opera_id: UUID, resource_id: UUID):
    """
    下载资源文件
    
    参数:
        opera_id (UUID): src ID
        resource_id (UUID): 资源文件ID
        
    返回:
        bytes: 文件内容流
        
    错误:
        404: 找不到指定的Opera或资源文件
    """
    pass

@router.put("/{resource_id}", status_code=204)
async def update_resource(opera_id: UUID, resource_id: UUID, resource: ResourceForUpdate):
    """
    更新资源文件
    
    注意:
        如需更新资源文件内容，应先将文件上传为临时文件

    参数:
        opera_id (UUID): src ID
        resource_id (UUID): 资源ID
        resource (ResourceForUpdate): 资源更新信息
            - name (str, optional): 资源名称
            - description (str, optional): 资源描述
            - mime_type (str, optional): MIME类型
            - last_update_staff_name (str): 最后更新者名称
            - temp_file_id (UUID, optional): 临时文件ID

    返回:
        204: 更新成功
        
    错误:
        404: 找不到指定的Opera或资源
        400: 更新失败时返回错误信息
    """
    pass

@router.delete("/{resource_id}", status_code=204)
async def delete_resource(opera_id: UUID, resource_id: UUID):
    """
    删除资源文件

    参数:
        opera_id (UUID): src ID
        resource_id (UUID): 资源文件ID

    返回:
        204: 删除成功

    错误:
        404: 找不到指定的Opera或资源文件
        400: 删除失败时返回错误信息
    """
    pass