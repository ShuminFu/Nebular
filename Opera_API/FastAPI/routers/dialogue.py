from fastapi import APIRouter, HTTPException
from typing import List, Optional
from uuid import UUID
from models import Dialogue, DialogueForCreation, DialogueForFilter

router = APIRouter(
    prefix="/Opera/{opera_id}/Dialogue",
    tags=["Dialogue"]
)

@router.get("/", response_model=List[Dialogue])
async def get_all_dialogues(opera_id: UUID):
    """
    获取所有对话
    
    参数:
        opera_id (UUID): Opera ID
        
    返回:
        List[Dialogue]: 对话列表，每个对话包含:
            - index (int): 对话索引
            - time (datetime): 对话时间
            - stage_index (int, optional): 场幕索引
            - staff_id (UUID, optional): 职员ID
            - is_narratage (bool): 是否为旁白
            - is_whisper (bool): 是否为悄悄话
            - text (str): 对话内容
            - tags (str, optional): 标签
            - mentioned_staff_ids (List[UUID], optional): 提到的职员ID列表
            
    错误:
        404: 找不到指定的Opera
    """
    pass

@router.get("/{dialogue_index}", response_model=Dialogue)
async def get_dialogue(opera_id: UUID, dialogue_index: int):
    """
    获取指定对话
    
    参数:
        opera_id (UUID): Opera ID
        dialogue_index (int): 对话索引
        
    返回:
        Dialogue: 对话信息，包含:
            - index (int): 对话索引
            - time (datetime): 对话时间
            - stage_index (int, optional): 场幕索引
            - staff_id (UUID, optional): 职员ID
            - is_narratage (bool): 是否为旁白
            - is_whisper (bool): 是否为悄悄话
            - text (str): 对话内容
            - tags (str, optional): 标签
            - mentioned_staff_ids (List[UUID], optional): 提到的职员ID列表
            
    错误:
        404: 找不到指定的Opera或对话
    """
    pass

@router.post("/Get", response_model=List[Dialogue])
async def get_filtered_dialogues(opera_id: UUID, filter: Optional[DialogueForFilter] = None):
    """
    按条件获取对话列表

    参数:
        opera_id (UUID): Opera ID
        filter (DialogueForFilter, optional): 过滤条件
            - index_not_before (int, optional): 起始索引(包含)
            - index_not_after (int, optional): 结束索引(包含)
            - top_limit (int, optional): 返回记录数上限，默认100
            - stage_index (int, optional): 指定场幕索引
            - includes_stage_index_null (bool): 是否包含无场幕的对话
            - includes_narratage (bool): 是否包含旁白
            - includes_for_staff_id_only (UUID, optional): 仅包含指定职员的对话
            - includes_staff_id_null (bool): 是否包含无职员的对话

    返回:
        List[Dialogue]: 对话列表，每个对话包含:
            - index (int): 对话索引
            - time (datetime): 对话时间
            - stage_index (int, optional): 场幕索引
            - staff_id (UUID, optional): 职员ID
            - is_narratage (bool): 是否为旁白
            - is_whisper (bool): 是否为悄悄话
            - text (str): 对话内容
            - tags (str, optional): 标签
            - mentioned_staff_ids (List[UUID], optional): 提到的职员ID列表

    错误:
        404: 找不到指定的Opera
    """
    pass

@router.post("/", response_model=Dialogue)
async def create_dialogue(opera_id: UUID, dialogue: DialogueForCreation):
    """
    创建对话
    
    参数:
        opera_id (UUID): Opera ID
        dialogue (DialogueForCreation): 对话创建信息
            - is_stage_index_null (bool): 是否不关联场幕
            - staff_id (UUID, optional): 职员ID
            - is_narratage (bool): 是否为旁白
            - is_whisper (bool): 是否为悄悄话
            - text (str): 对话内容
            - tags (str, optional): 标签
            - mentioned_staff_ids (List[UUID], optional): 提到的职员ID列表
            
    返回:
        Dialogue: 创建的对话信息，包含:
            - index (int): 对话索引
            - time (datetime): 对话时间
            - stage_index (int, optional): 场幕索引
            - staff_id (UUID, optional): 职员ID
            - is_narratage (bool): 是否为旁白
            - is_whisper (bool): 是否为悄悄话
            - text (str): 对话内容
            - tags (str, optional): 标签
            - mentioned_staff_ids (List[UUID], optional): 提到的职员ID列表
            
    错误:
        404: 找不到指定的Opera
        400: 创建失败时返回错误信息
    """
    pass