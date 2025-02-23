"""CR匹配器的CrewBase实现"""

from crewai import Agent, Crew, Task, Process
from crewai.project import CrewBase, agent, crew, task
from src.crewai_ext.config.llm_setup import llm
from pydantic import BaseModel, Field

class CRMatchingResult(BaseModel):
    """CR匹配结果模型"""
    selected_cr: str = Field(..., description="选中的CR信息")

@CrewBase
class CRMatcherCrew:
    """CR匹配器Crew

    负责根据任务需求和CR的专长选择最合适的CrewRunner。
    使用LLM分析任务需求和CR配置，计算匹配度并给出选择理由。

    Required Inputs:
    - task_type: 任务类型
    - task_priority: 任务优先级
    - code_details: 代码生成任务的详细信息
    - opera_id: 目标Opera ID
    - cr_list: 可用的CR列表
    """

    agents_config = "../config/cr_matcher/agents.yaml"
    tasks_config = "../config/cr_matcher/tasks.yaml"

    @agent
    def cr_matcher(self) -> Agent:
        """创建CR匹配专家Agent"""
        return Agent(
            config=self.agents_config["cr_matcher"],
            llm=llm,
            verbose=True
        )

    @task
    def match_cr(self) -> Task:
        """创建CR匹配任务，通过crew kickoff inputs接收参数"""
        return Task(
            config=self.tasks_config["cr_matching_task"],
            output_json=CRMatchingResult
        )

    @crew
    def crew(self) -> Crew:
        """创建CR匹配Crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True
        ) 