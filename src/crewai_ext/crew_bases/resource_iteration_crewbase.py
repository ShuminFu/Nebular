from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from src.crewai_ext.config.llm_setup import llm
from pydantic import BaseModel, Field, StrictStr
from typing import List, Dict, Any
from src.crewai_ext.tools.opera_api.resource_api_tool import ResourceTool

class IterationAnalysisInputs(BaseModel):
    """迭代分析任务的输入参数验证模型"""

    iteration_requirement: StrictStr = Field(..., description="迭代需求描述")
    resource_list: List[Dict[str, str]] = Field(...,
        description="包含file_path和resource_id的资源列表，示例: [{'file_path': 'src/html/index.html', 'resource_id': 'uuid'}]")


class IterationAnalysisResult(BaseModel):
    """迭代分析需求，分解任务每个任务修改一个文件"""
    
    tasks: List[Dict[str, Any]] = Field(...,
        description="包含以下字段的任务列表："
        "file_path: 文件路径, "
        "resource_id: 资源ID, "
        "action: 操作类型, "
        "position: 修改位置, "
        "task_description: 任务需求描述, ")


@CrewBase
class IterationAnalyzerCrew:
    """迭代分析Crew

    负责分析代码迭代需求，将大型迭代任务分解为小型任务，并进行依赖分析。
    使用LLM分析代码结构、识别关键修改点，评估潜在风险。

    Required Inputs:
    - requirement: 迭代需求描述
    - tags: 对话标签
    """

    agents_config = "../config/resource_iteration/iteration_agents.yaml"
    tasks_config = "../config/resource_iteration/iteration_tasks.yaml"

    @agent
    def task_decomposer(self) -> Agent:
        """创建任务分解专家Agent"""
        return Agent(config=self.agents_config["task_decomposer"], llm=llm, tools=[ResourceTool()], verbose=True)

    @task
    def decompose_tasks(self) -> Task:
        """创建任务分解任务"""
        return Task(config=self.tasks_config["task_decomposition_task"])

    @crew
    def crew(self) -> Crew:
        """创建迭代分析Crew"""
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)
