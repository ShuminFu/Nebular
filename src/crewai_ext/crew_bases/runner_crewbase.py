from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from pydantic import BaseModel, Field, StrictStr
from src.crewai_ext.config.llm_setup import llm
from typing import List, Optional

class ResourceItem(BaseModel):
    """资源项数据结构"""

    file_path: StrictStr = Field(..., description="文件路径")
    type: StrictStr = Field(..., description="资源类型")
    mime_type: StrictStr = Field(..., description="MIME类型")
    description: StrictStr = Field(..., description="资源描述")

class GenerationInputs(BaseModel):
    """代码生成任务的输入参数验证模型"""

    file_path: StrictStr = Field(..., description="目标文件路径")
    file_type: StrictStr = Field(..., description="文件类型（扩展名）")
    requirement: StrictStr = Field(..., description="需求描述文本")
    project_type: StrictStr = Field(..., description="项目类型")
    project_description: Optional[StrictStr] = Field(None, description="项目描述信息，可为空")
    frameworks: List[StrictStr] = Field(default_factory=list, description="使用的框架列表")
    resources: List[ResourceItem] = Field(default_factory=list, description="相关资源文件信息列表")  # 修改数据结构
    references: List[StrictStr] = Field(default_factory=list, description="引用关系列表")


@CrewBase
class RunnerCrew:
    agents_config = "../config/crew_runner/agents.yaml"
    tasks_config = "../config/crew_runner/tasks.yaml"

    @agent
    def code_generator(self) -> Agent:
        """Create an xxx"""
        return Agent(config=self.agents_config["code_generator"], llm=llm, verbose=True)

    @task
    def generation_task(self) -> Task:
        """Create an xxx."""
        return Task(config=self.tasks_config["code_generation_task"])

    @crew
    def crew(self) -> Crew:
        """Creates xxx Crew"""
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)
