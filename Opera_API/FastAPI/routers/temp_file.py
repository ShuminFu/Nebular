from fastapi import APIRouter, HTTPException, Body
from typing import Optional
from uuid import UUID
from models import TempFile

router = APIRouter(
    prefix="/TempFile",
    tags=["TempFile"]
)

@router.post("/", response_model=TempFile)
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
            - id (UUID): 临时文件ID
            - length (int): 当前文件总长度

    错误:
        404: 指定的临时文件不存在
        400: 上传失败时返回错误信息
    """
    pass

@router.post("/{temp_file_id}", response_model=TempFile)
async def append_temp_file(temp_file_id: UUID, file: bytes = Body(...)):
    """
    附加临时文件数据块

    参数:
        temp_file_id (UUID): 临时文件ID
        file (bytes): 要附加的文件数据块(chunk)

    返回:
        TempFile: 临时文件信息
            - id (UUID): 临时文件ID
            - length (int): 当前文件总长度

    错误:
        404: 指定的临时文件不存在
        400: 上传失败时返回错误信息
    """
    pass

@router.delete("/{temp_file_id}", status_code=204)
async def delete_temp_file(temp_file_id: UUID):
    """
    删除临时文件

    参数:
        temp_file_id (UUID): 要删除的临时文件ID

    返回:
        204: 删除成功

    错误:
        404: 指定的临时文件不存在
    """
    pass