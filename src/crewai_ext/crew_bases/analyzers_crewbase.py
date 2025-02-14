from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from src.crewai_ext.config.llm_setup import llm
from src.crewai_ext.tools.opera_api.dialogue_api_tool import _SHARED_DIALOGUE_TOOL
from src.crewai_ext.tools.utils.utility_tools import UUIDGeneratorTool
from src.core.dialogue.output_json_models import (
    IntentAnalysisResult,
    ContextStructure,
)
from pydantic import BaseModel, Field, StrictBool, StrictStr
from typing import List, Optional, Dict
from datetime import datetime

class IntentAnalysisInputs(BaseModel):
    """IntentAnalysisInputs验证模型"""

    text: StrictStr = Field(..., description="对话内容文本")
    type: StrictStr = Field(..., description="对话类型")
    is_narratage: StrictBool = Field(..., description="是否为旁白标记")
    is_whisper: StrictBool = Field(..., description="是否为悄悄话标记")
    tags: Optional[str] = Field(default_factory=None, description="对话标签列表")
    mentioned_staff_bools: bool = Field(default_factory=list, description="提及其他Staff的标记")
    opera_id: Optional[StrictStr] = Field(None, description="当前Opera的ID")
    dialogue_index: Optional[int] = Field(None, description="对话索引号")
    stage_index: Optional[int] = Field(None, description="对话阶段索引")
    dialogue_same_stage: Optional[List[Dict]] = Field(None, description="同阶段对话内容")
    timestamp: Optional[float] = Field(
        default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"), description="时间戳，格式为YYYYMMDD_HHMMSS"
    )


class ContextAnalysisInputs(BaseModel):
    """ContextAnalysisInputs验证模型"""

    opera_id: str = Field(..., description="当前Opera的ID")
    dialogue_index: int = Field(..., description="对话索引号")
    text: StrictStr = Field(..., description="对话内容文本")
    type: StrictStr = Field(..., description="对话类型名称")
    tags: Optional[str] = Field(default_factory=None, description="对话标签列表")
    stage_index: Optional[int] = Field(..., description="对话阶段索引")
    intent_analysis: Optional[str] = Field(..., description="意图分析结果")
    dialogue_same_stage: List[Dict] = Field(..., description="同阶段对话内容列表")


@CrewBase
class IntentAnalyzerCrew:
    """Dialogue Analysis Crew for analyzing intents and context

    Required Inputs:
    - text: 对话内容文本
    - type: 对话类型
    - is_narratage: 是否为旁白标记
    - is_whisper: 是否为悄悄话标记
    - tags: 对话标签列表
    - mentioned_staff_bools: 提及其他Staff的标记
    - timestamp: 当前时间戳
    """

    agents_config = "../config/analyzer/intent_agents.yaml"
    tasks_config = "../config/analyzer/intent_tasks.yaml"

    @agent
    def intent_analyzer(self) -> Agent:
        """Create an intent analyzer agent."""
        return Agent(config=self.agents_config["intent_analyzer"], llm=llm, tools=[_SHARED_DIALOGUE_TOOL], verbose=True)

    @task
    def analyze_intent(self) -> Task:
        """Create an intent analysis task that will receive parameters through crew kickoff inputs."""
        return Task(config=self.tasks_config["intent_analysis_task"], output_json=IntentAnalysisResult)

    @crew
    def crew(self) -> Crew:
        """Creates the Dialogue Analysis Crew"""
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)


@CrewBase
class ContextAnalyzerCrew:
    """Dialogue Analysis Crew for analyzing intents and context

    Required Inputs:
    当前对话：
    - Opera ID: opera_id
    - 索引：dialogue_index
    - 内容：text
    - 类型：type
    - 标签：tags
    - 阶段：stage_index
    - 意图：intent_analysis

    同阶段的对话：dialogue_same_stage
    """

    agents_config = "../config/analyzer/context_agents.yaml"
    tasks_config = "../config/analyzer/context_tasks.yaml"

    @agent
    def context_analyzer(self) -> Agent:
        """Create a context analyzer agent."""
        return Agent(
            config=self.agents_config["context_analyzer"],
            llm=llm,
            tools=[_SHARED_DIALOGUE_TOOL, UUIDGeneratorTool()],
            verbose=True,
        )

    @task
    def analyze_context_index(self) -> Task:
        """Create a context indexing task that will receive parameters through crew kickoff inputs."""
        return Task(
            config=self.tasks_config["index_task"],
        )

    @task
    def analyze_context_structure(self) -> Task:
        """Create a context structure analysis task that will receive parameters through crew kickoff inputs."""
        return Task(config=self.tasks_config["context_structure_task"], output_json=ContextStructure)

    @crew
    def crew(self) -> Crew:
        """Creates the Context Analysis Crew"""
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)
