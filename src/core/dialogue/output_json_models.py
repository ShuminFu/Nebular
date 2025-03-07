"""
对话分析输出模型

此模块包含所有用于CrewAI任务输出的Pydantic模型。
这些模型用于:
1. 意图分析结果
2. 上下文分析结果
3. 代码生成相关结构
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class CodeResource(BaseModel):
    """代码资源文件模型"""
    file_path: str
    type: str
    mime_type: str
    description: str
    references: Optional[List[str]] = Field(default_factory=list)


class CodeDetails(BaseModel):
    """代码详情模型"""
    project_type: str
    project_description: str
    resources: List[CodeResource]
    requirements: List[str]
    frameworks: List[str]


class IntentAnalysisResult(BaseModel):
    """意图分析结果模型"""
    intent: str
    reason: Optional[str] = None
    is_code_request: bool = False
    code_details: Optional[CodeDetails] = None


class DecisionPoint(BaseModel):
    """决策点模型"""
    decision: str
    reason: str
    dialogue_index: str
    topic_id: str


class ConversationFlow(BaseModel):
    """对话流程模型"""
    current_topic: str
    topic_id: str
    topic_type: str
    status: str
    derived_from: Optional[str] = None
    change_reason: Optional[str] = None
    evolution_chain: List[str]
    previous_topics: List[str]


class CodeContext(BaseModel):
    """代码上下文模型"""
    requirements: List[str]
    frameworks: List[str]
    file_structure: List[str]
    api_choices: List[str]


class ContextStructure(BaseModel):
    """上下文结构模型"""
    conversation_flow: ConversationFlow
    code_context: CodeContext
    decision_points: DecisionPoint


class DialogueIndices(BaseModel):
    """对话索引模型"""
    related_indices: str
