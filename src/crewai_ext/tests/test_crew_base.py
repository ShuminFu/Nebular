from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from typing import Optional, Dict, Any
from src.crewai_ext.config.llm_setup import llm
# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators


@CrewBase
class TemplateCrew:
    """Poem Crew"""

    # Learn more about YAML configuration files here:
    # Agents: https://docs.crewai.com/concepts/agents#yaml-configuration-recommended
    # Tasks: https://docs.crewai.com/concepts/tasks#yaml-configuration-recommended
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # If you would lik to add tools to your crew, you can learn more about it here:
    # https://docs.crewai.com/concepts/agents#agent-tools
    @agent
    def poem_writer(self) -> Agent:
        return Agent(
            config=self.agents_config["poem_writer"],
        )

    # To learn more about structured task outputs,
    # task dependencies, and task callbacks, check out the documentation:
    # https://docs.crewai.com/concepts/tasks#overview-of-a-task
    @task
    def write_poem(self) -> Task:
        return Task(
            config=self.tasks_config["write_poem"],
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Research Crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

        return Crew(
            agents=self.agents,  # Automatically created by the @agent decorator
            tasks=self.tasks,  # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
        )


@CrewBase
class DynamicCrew:
    """Dynamic Crew for testing parameter passing"""

    agents_config = "../config/agents.yaml"
    tasks_config = "../config/tasks.yaml"

    def __init__(self, topic="AI Technology", extra_context: Optional[Dict[str, Any]] = None):
        self.topic = topic
        self.extra_context = extra_context or {}

    @agent
    def researcher(self) -> Agent:
        """Create a researcher agent with dynamic topic"""
        return Agent(config=self.agents_config["researcher"], llm=llm)

    @agent
    def reporting_analyst(self) -> Agent:
        """Create a reporting analyst with dynamic topic"""
        return Agent(config=self.agents_config["reporting_analyst"], llm=llm)

    @task
    def research_task(self, additional_context: str = "", custom_output_format: str = "") -> Task:
        """Create a research task with dynamic topic and additional context

        Args:
            additional_context: 额外的上下文信息
            custom_output_format: 自定义输出格式要求
        """
        # 基础配置
        base_config = self.tasks_config["research_task"]

        # 扩展description
        description = f"{base_config['description']}\n"
        if additional_context:
            description += f"\nAdditional Context:\n{additional_context}"

        # 扩展expected_output
        expected_output = base_config["expected_output"]
        if custom_output_format:
            expected_output = f"{expected_output}\n\nOutput Format Requirements:\n{custom_output_format}"

        # 构建上下文
        context = []  # context: Optional[List["Task"]]
        # 创建任务配置
        task_config = {
            "description": description,
            "expected_output": expected_output,
            "agent": self.researcher(),
        }

        # 创建任务
        task = Task(
            config=task_config,
        )

        return task

    @task
    def reporting_task(self, analysis_requirements: Optional[str] = None) -> Task:
        """Create a reporting task with dynamic requirements

        Args:
            analysis_requirements: 额外的分析要求列表
        """
        base_config = self.tasks_config["reporting_task"]

        # 扩展description
        description = base_config["description"]
        if analysis_requirements:
            requirements_text = "\n".join(f"- {req}" for req in analysis_requirements)
            description += f"\n\nAdditional Analysis Requirements:\n{requirements_text}"

        # 构建上下文
        context = []
        if analysis_requirements:
            context.extend(analysis_requirements)
        if self.extra_context:
            context.extend(f"{k}: {v}" for k, v in self.extra_context.items())

        task = Task(
            config={
                "description": description,
                "expected_output": base_config["expected_output"],
                "agent": "reporting_analyst",
            },
            agent=self.reporting_analyst(),
        )
        return task

    @crew
    def crew(self) -> Crew:
        """Creates the Research Crew"""
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)


def test_dynamic_crew():
    # 创建一个动态Crew实例，传入特定主题和额外上下文
    extra_context = {
        "background_info": "This research is part of a larger quantum computing initiative",
        "target_audience": "Technical experts in the field",
    }

    dynamic_crew = DynamicCrew(topic="Quantum Computing", extra_context=extra_context)

    # 使用额外参数创建任务
    research_task = dynamic_crew.research_task(
        additional_context="Focus on recent breakthroughs in quantum error correction",
        custom_output_format="Include code examples where applicable",
    )

    reporting_task = dynamic_crew.reporting_task(
        analysis_requirements="Compare performance metrics with classical computing",
    )

    # 验证参数是否正确传递
    assert "recent breakthroughs" in research_task.description
    assert "code examples" in research_task.expected_output
    result = dynamic_crew.crew().kickoff(inputs={"topic": "AI Agents"})
    print(result)


if __name__ == "__main__":
    test_dynamic_crew()
