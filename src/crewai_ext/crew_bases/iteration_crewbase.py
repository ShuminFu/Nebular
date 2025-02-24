from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from src.crewai_ext.config.llm_setup import llm
from pydantic import BaseModel, Field, StrictStr
from typing import List, Optional, Dict, Any


class IterationAnalysisInputs(BaseModel):
    """迭代分析任务的输入参数验证模型"""

    file_path: StrictStr = Field(..., description="需要迭代的文件路径")
    current_content: StrictStr = Field(..., description="当前文件内容")
    requirement: StrictStr = Field(..., description="迭代需求描述")
    project_type: StrictStr = Field(..., description="项目类型")
    frameworks: List[StrictStr] = Field(default_factory=list, description="使用的框架列表")
    dependencies: List[StrictStr] = Field(default_factory=list, description="项目依赖列表")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="额外的上下文信息")


class IterationAnalysisResult(BaseModel):
    """迭代分析结果模型"""

    tasks: List[Dict[str, Any]] = Field(..., description="分解后的任务列表")
    analysis: Dict[str, Any] = Field(..., description="代码分析结果")
    dependencies: List[str] = Field(..., description="识别出的依赖关系")
    risks: List[str] = Field(..., description="潜在风险点")
    suggestions: List[str] = Field(..., description="改进建议")


@CrewBase
class IterationAnalyzerCrew:
    """迭代分析Crew

    负责分析代码迭代需求，将大型迭代任务分解为小型任务，并进行依赖分析。
    使用LLM分析代码结构、识别关键修改点，评估潜在风险。

    Required Inputs:
    - file_path: 需要迭代的文件路径
    - current_content: 当前文件内容
    - requirement: 迭代需求描述
    - project_type: 项目类型
    - frameworks: 使用的框架列表
    - dependencies: 项目依赖列表
    - context: 额外的上下文信息
    """

    agents_config = "../config/analyzer/iteration_agents.yaml"
    tasks_config = "../config/analyzer/iteration_tasks.yaml"

    @agent
    def task_decomposer(self) -> Agent:
        """创建任务分解专家Agent"""
        return Agent(config=self.agents_config["task_decomposer"], llm=llm, verbose=True)

    @task
    def decompose_tasks(self) -> Task:
        """创建任务分解任务"""
        return Task(config=self.tasks_config["task_decomposition_task"])

    @crew
    def crew(self) -> Crew:
        """创建迭代分析Crew"""
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)
