from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from src.crewai_ext.config.llm_setup import llm
from src.crewai_ext.tools.opera_api.dialogue_api_tool import _SHARED_DIALOGUE_TOOL
from src.crewai_ext.tools.utils.utility_tools import UUIDGeneratorTool
from src.core.dialogue.output_json_models import (
    IntentAnalysisResult,
    ContextStructure,
)


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

    agents_config = "../config/agents.yaml"
    tasks_config = "../config/tasks.yaml"

    def __init__(self, opera_id: str = None, dialogue_index: int = None):
        self.opera_id = opera_id
        self.dialogue_index = dialogue_index

    @agent
    def intent_analyzer(self) -> Agent:
        """Create an intent analyzer agent."""
        return Agent(config=self.agents_config["intent_analyzer"], llm=llm, tools=[_SHARED_DIALOGUE_TOOL], verbose=True)

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
    def analyze_intent(self) -> Task:
        """Create an intent analysis task that will receive parameters through crew kickoff inputs."""
        return Task(config=self.tasks_config["intent_analysis_task"], output_json=IntentAnalysisResult)

    @task
    def analyze_context_index(self) -> Task:
        """Create a context indexing task that will receive parameters through crew kickoff inputs."""
        return Task(
            config=self.tasks_config["index_task"],
        )

    @task
    def analyze_context_structure(self) -> Task:
        """Create a context structure analysis task that will receive parameters through crew kickoff inputs."""
        return Task(
            config=self.tasks_config["context_structure_task"],
        )

    @crew
    def intent_crew(self) -> Crew:
        """Creates the Dialogue Analysis Crew"""
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)
