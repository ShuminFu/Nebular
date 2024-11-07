from fastapi import APIRouter, HTTPException
from typing import List, Optional
from uuid import UUID
from models import StaffInvitation, StaffInvitationForCreation, StaffInvitationForAcceptance

router = APIRouter(
    prefix="/Opera/{opera_id}/StaffInvitation",
    tags=["StaffInvitation"]
)

@router.get("/", response_model=List[StaffInvitation])
async def get_all_staff_invitations(opera_id: UUID):
    """
    获取所有职员邀请
    
    参数:
        opera_id (UUID): Opera ID
        
    返回:
        List[StaffInvitation]: 职员邀请列表，包含:
            - id (UUID): 邀请ID
            - bot_id (UUID): Bot ID
            - parameter (str): 参数
            - tags (str): 标签
            - roles (str): 角色
            - permissions (str): 权限
            
    错误:
        404: 找不到指定的Opera
    """
    return [
        StaffInvitation(
            id=UUID('12345678-1234-5678-1234-567812345678'),
            bot_id=UUID('87654321-4321-8765-4321-987654321098'),
            parameter="default_parameter",
            tags="tag1,tag2",
            roles="role1,role2",
            permissions="permission1,permission2"
        )
    ]

@router.get("/{invitation_id}", response_model=StaffInvitation)
async def get_staff_invitation(opera_id: UUID, invitation_id: UUID):
    """
    获取指定职员邀请
    
    参数:
        opera_id (UUID): Opera ID
        invitation_id (UUID): 邀请ID
        
    返回:
        StaffInvitation: 职员邀请信息
        
    错误:
        404: 找不到指定的Opera或邀请
    """
    if not opera_id or not invitation_id:
        raise HTTPException(status_code=404, detail="Opera或邀请不存在")
    
    return StaffInvitation(
        id=invitation_id,
        bot_id=UUID('87654321-4321-8765-4321-987654321098'),
        parameter="default_parameter",
        tags="tag1,tag2",
        roles="role1,role2",
        permissions="permission1,permission2"
    )

@router.post("/", response_model=StaffInvitation)
async def create_staff_invitation(opera_id: UUID, invitation: StaffInvitationForCreation):
    """
    创建职员邀请
    
    参数:
        opera_id (UUID): Opera ID
        invitation (StaffInvitationForCreation): 邀请创建信息
            - bot_id (UUID): Bot ID
            - parameter (str): 参数
            - tags (str): 标签
            - roles (str): 角色
            - permissions (str): 权限
            
    返回:
        StaffInvitation: 创建的邀请信息
        
    错误:
        404: 找不到指定的Opera
        400: 创建失败时返回错误信息
    """
    if not opera_id:
        raise HTTPException(status_code=404, detail="Opera不存在")
    
    return StaffInvitation(
        id=UUID('12345678-1234-5678-1234-567812345678'),
        bot_id=invitation.bot_id,
        parameter=invitation.parameter,
        tags=invitation.tags,
        roles=invitation.roles,
        permissions=invitation.permissions
    )

@router.delete("/{invitation_id}", status_code=204)
async def delete_staff_invitation(opera_id: UUID, invitation_id: UUID):
    """
    删除职员邀请
    
    参数:
        opera_id (UUID): Opera ID
        invitation_id (UUID): 邀请ID
        
    返回:
        204: 删除成功
        
    错误:
        404: 找不到指定的Opera或邀请
        400: 删除失败时返回错误信息
    """
    if not opera_id or not invitation_id:
        raise HTTPException(status_code=404, detail="Opera或邀请不存在")
    return None

@router.post("/{invitation_id}/Accept", response_model=UUID)
async def accept_staff_invitation(opera_id: UUID, invitation_id: UUID, acceptance: StaffInvitationForAcceptance):
    """
    接受职员邀请

    参数:
        opera_id (UUID): Opera ID
        invitation_id (UUID): 邀请ID
        acceptance (StaffInvitationForAcceptance): 接受邀请的信息
            - name (str): 职员名称
            - parameter (str, optional): 职员参数，未指定则使用邀请中的值
            - is_on_stage (bool): 是否在台上
            - tags (str, optional): 标签，未指定则使用邀请中的值
            - roles (str, optional): 角色，未指定则使用邀请中的值
            - permissions (str, optional): 权限，未指定则使用邀请中的值

    返回:
        UUID: 创建的职员ID

    错误:
        404: 找不到指定的Opera或邀请
        400: 接受邀请失败时返回错误信息

    注意:
        此功能的ETag为职员Id，而非职员邀请Id
    """
    if not opera_id or not invitation_id:
        raise HTTPException(status_code=404, detail="Opera或邀请不存在")
    
    return UUID('12345678-1234-5678-1234-567812345678')