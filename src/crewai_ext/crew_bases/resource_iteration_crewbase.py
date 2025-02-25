from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from src.crewai_ext.config.llm_setup import llm
from pydantic import BaseModel, Field, StrictStr
from typing import List, Dict, Optional
from src.crewai_ext.tools.opera_api.resource_api_tool import ResourceTool


class IterationAnalysisInputs(BaseModel):
    """迭代分析任务的输入参数验证模型"""

    iteration_requirement: StrictStr = Field(..., description="迭代需求描述")
    resource_list: List[Dict[str, str]] = Field(...,
        description="包含file_path和resource_id的资源列表，示例: [{'file_path': 'src/html/index.html', 'resource_id': 'uuid'}]")


class Resource(BaseModel):
    """资源文件信息模型"""

    file_path: str = Field(..., description="文件路径（如/src/html/index.html）")
    type: str = Field(..., description="根据文件扩展名确定类型如html")
    mime_type: str = Field(..., description="根据文件类型确定（如text/html）")
    description: str = Field(..., description="针对任务需求，要对这个资源进行怎样的操作和改动的描述")
    action: str = Field(..., description="操作类型：create|update|delete")
    resource_id: str = Field(..., description="资源ID")
    position: str = Field(..., description="如果是修改，指出有问题的修改位置。如果是新增或者删除则为全部")


class CodeDetails(BaseModel):
    """代码详情模型"""

    project_type: str = Field(default="迭代项目", description="项目类型")
    project_description: str = Field(default="基于迭代需求对多个资源进行修改", description="项目整体描述")
    resources: List[Resource] = Field(default_factory=list, description="需要修改的资源列表")
    requirements: List[str] = Field(default_factory=list, description="从迭代需求中提取的核心要求列表")
    frameworks: List[str] = Field(default_factory=list, description="涉及到的框架列表")


class IterationAnalysisResult(BaseModel):
    """迭代分析结果模型，与IntentAnalysisResult结构保持一致"""

    intent: str = Field(default="resource_iteration", description="意图描述")
    reason: Optional[str] = Field(default="基于迭代需求的资源修改任务", description="分析原因")
    is_code_request: bool = Field(default=True, description="是否为代码请求")
    code_details: Optional[CodeDetails] = Field(default=None, description="代码详情信息")


@CrewBase
class IterationAnalyzerCrew:
    """迭代分析Crew

    负责分析代码迭代需求，将大型迭代任务分解为小型任务，并进行依赖分析。
    使用LLM分析代码结构、识别关键修改点，评估潜在风险。

    Required Inputs:
    - requirement: 迭代需求描述
    - tags: 对话标签
    """

    agents_config = "../config/resource_iteration/agents.yaml"
    tasks_config = "../config/resource_iteration/tasks.yaml"

    @agent
    def task_decomposer(self) -> Agent:
        """创建任务分解专家Agent"""
        return Agent(config=self.agents_config["task_decomposer"], llm=llm, tools=[ResourceTool()], verbose=True)

    @task
    def decompose_tasks(self) -> Task:
        """创建任务分解任务"""
        return Task(config=self.tasks_config["task_decomposition_task"], output_json=IterationAnalysisResult)

    @crew
    def crew(self) -> Crew:
        """创建迭代分析Crew"""
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)
