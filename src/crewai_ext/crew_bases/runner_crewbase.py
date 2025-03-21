from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from pydantic import BaseModel, Field, StrictStr
from src.crewai_ext.config.llm_setup import llm
from typing import List, Optional, Type, Dict, Any

class ChatReply(BaseModel):
    """对话回复模型"""
    reply_text: str
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
class RunnerCodeGenerationCrew:
    agents_config = "../config/crew_runner/agents.yaml"
    tasks_config = "../config/crew_runner/tasks.yaml"

    @classmethod
    def create_dynamic_crew(cls, config: Dict[str, Any]) -> Type["RunnerCodeGenerationCrew"]:
        """工厂方法创建动态配置的Crew类

        Args:
            config: 包含agents和tasks配置的字典

        Returns:
            动态生成的Crew子类
        """

        class DynamicCrew(RunnerCodeGenerationCrew):
            _dynamic_config = config  # 类级别配置存储

            def __init__(self):
                super().__init__()

            def load_configurations(self):
                """Override配置加载方法"""
                self.agents_config = self._dynamic_config.get("agents", {})
                self.tasks_config = self._dynamic_config.get("tasks", {})

        return DynamicCrew

    @agent
    def code_generator(self) -> Agent:
        """Create a code generation agent with validation capabilities"""
        return Agent(config=self.agents_config["code_generator"], tools=[], llm=llm, verbose=True)

    @task
    def generation_task(self) -> Task:
        """Create a multi-file code generation task with resource dependencies"""
        return Task(config=self.tasks_config["code_generation_task"])

    @crew
    def crew(self) -> Crew:
        """Creates code generation crew with validation workflow"""

        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)


@CrewBase
class RunnerChatCrew:
    agents_config = "../config/crew_runner/agents.yaml"
    tasks_config = "../config/crew_runner/tasks.yaml"

    @agent
    def code_generator(self) -> Agent:
        """Create a code generation agent with validation capabilities"""
        return Agent(config=self.agents_config["code_generator"], llm=llm, verbose=True)

    @task
    def chat_task(self) -> Task:
        """Create a chat task"""
        return Task(config=self.tasks_config["chat_task"], output_json=ChatReply)

    @crew
    def crew(self) -> Crew:
        """Creates chat crew"""
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)
