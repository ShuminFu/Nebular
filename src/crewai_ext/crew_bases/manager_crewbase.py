from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from src.crewai_ext.config.llm_setup import llm
from src.crewai_ext.tools.opera_api.bot_api_tool import BotTool
from uuid import UUID
from pydantic import BaseModel, Field
from typing import Dict, List, Any

class ChatReply(BaseModel):
    """对话回复模型"""
    reply_text: str
class CrewRunnerConfig(BaseModel):
    agents: Dict[str, Dict[str, Any]] = Field(..., description="Agents配置字典，格式为 {agent_name: config_dict}")
    tasks: Dict[str, Dict[str, Any]] = Field(..., description="Tasks配置字典，格式为 {task_name: config_dict}")

class MultiCrewConfigOutput(BaseModel):
    """支持多CrewRunner的配置输出模型"""

    runners: List[CrewRunnerConfig] = Field(..., description="多个CrewRunner的配置集合", min_items=1)


@CrewBase
class ManagerCrew:
    agents_config = "../config/crew_manager/agents.yaml"
    tasks_config = "../config/crew_manager/tasks.yaml"
    bot_config = "../config/crew_manager/bot.yaml"

    def get_bot_id(self) -> UUID:
        """从配置文件中获取bot_id"""
        import yaml
        from pathlib import Path

        config_path = Path(__file__).parent / self.bot_config
        with open(config_path) as f:
            bot_config = yaml.safe_load(f)

        if not (bot_id := bot_config.get("bot_id")):
            raise ValueError("bot_id not found in crew_manager/bot.yaml config")

        return UUID(bot_id)

    @agent
    def bot_manager(self) -> Agent:
        """Create an bot management agent"""
        return Agent(config=self.agents_config["bot_manager"], llm=llm, tools=[BotTool()], verbose=True)

    @task
    def check_bot_task(self) -> Task:
        """Create a bot health check task"""
        return Task(config=self.tasks_config["check_bot_task"])

    @crew
    def crew(self) -> Crew:
        """Creates bot management crew"""

        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)


@CrewBase
class ManagerChatCrew:
    agents_config = "../config/crew_manager/agents.yaml"
    tasks_config = "../config/crew_manager/tasks.yaml"
    bot_config = "../config/crew_manager/bot.yaml"

    def get_bot_id(self) -> UUID:
        """从配置文件中获取bot_id"""
        import yaml
        from pathlib import Path

        config_path = Path(__file__).parent / self.bot_config
        with open(config_path) as f:
            bot_config = yaml.safe_load(f)

        if not (bot_id := bot_config.get("bot_id")):
            raise ValueError("bot_id not found in crew_manager/bot.yaml config")

        return UUID(bot_id)

    @agent
    def bot_manager(self) -> Agent:
        """Create an bot management agent"""
        return Agent(config=self.agents_config["bot_manager"], llm=llm, tools=[BotTool()], verbose=True)

    @task
    def chat_task(self) -> Task:
        """Create a chat task"""
        return Task(config=self.tasks_config["chat_task"], output_json=ChatReply)
    @crew
    def crew(self) -> Crew:
        """Creates chat crew"""
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)

@CrewBase
class ManagerInitCrew:
    agents_config = "../config/crew_manager/agents.yaml"
    tasks_config = "../config/crew_manager/tasks.yaml"
    bot_config = "../config/crew_manager/bot.yaml"

    def get_bot_id(self) -> UUID:
        """从配置文件中获取bot_id"""
        import yaml
        from pathlib import Path

        config_path = Path(__file__).parent / self.bot_config
        with open(config_path) as f:
            bot_config = yaml.safe_load(f)

        if not (bot_id := bot_config.get("bot_id")):
            raise ValueError("bot_id not found in crew_manager/bot.yaml config")

        return UUID(bot_id)

    @agent
    def bot_manager(self) -> Agent:
        """Create an bot management agent"""
        return Agent(config=self.agents_config["bot_manager"], llm=llm, verbose=True)

    # @agent
    # def config_validator(self) -> Agent:
    #     """Create a crew runner config agent"""
    #     return Agent(config=self.agents_config["config_validator"], llm=llm, verbose=True)

    @task
    def init_task(self) -> Task:
        """Create a init task"""
        return Task(config=self.tasks_config["init_task"], output_json=MultiCrewConfigOutput)

    # @task
    # def config_validator_task(self) -> Task:
    #     """Create a config validator task"""
    #     return Task(config=self.tasks_config["config_validator_task"], output_json=MultiCrewConfigOutput)

    @crew
    def crew(self) -> Crew:
        """Creates init crew"""
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)