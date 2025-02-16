from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from src.crewai_ext.config.llm_setup import llm
from src.crewai_ext.tools.opera_api.bot_api_tool import BotTool
from uuid import UUID


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
        selected_agents = [
            agent for agent in self.agents 
            if agent.role == "bot_manager"
        ]
        selected_tasks = [
            task for task in self.tasks 
            if task.name == "check_bot_task"
        ]   
        return Crew(agents=selected_agents, tasks=selected_tasks, process=Process.sequential, verbose=True)

    @crew
    def chat_crew(self) -> Crew:
        """Creates chat crew"""
        selected_agents = [
            agent for agent in self.agents 
            if "bot_manager" in agent.role.strip().lower()
        ]
        selected_tasks = [
            task for task in self.tasks 
            if task.name == "chat_task"
        ]
        return Crew(agents=selected_agents, tasks=selected_tasks, process=Process.sequential, verbose=True)

