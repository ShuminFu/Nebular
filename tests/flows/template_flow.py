#!/usr/bin/env python
from typing import Dict, Any, List
from random import choice
from pydantic import BaseModel
from crewai.flow.flow import Flow, listen, start
from crewai.project import CrewBase, agent, crew, task
from crewai import Agent, Crew, Process, Task
from src.crewai_ext.config.llm_setup import llm

# 预定义的研究主题列表
RESEARCH_TOPICS = ["AI Technology", "Quantum Computing", "Blockchain", "Machine Learning", "Robotics"]


class DynamicResearchState(BaseModel):
    """动态研究流程的状态管理"""

    topic: str = ""
    extra_context: Dict[str, Any] = {}
    research_result: str = ""
    report_result: str = ""
    analysis_requirements: List[str] = []


@CrewBase
class ResearchCrew:
    """Research crew implementation using CrewBase pattern"""

    agents_config = "../config/agents.yaml"
    tasks_config = "../config/tasks.yaml"

    @agent
    def researcher(self) -> Agent:
        """Create a researcher agent"""
        return Agent(config=self.agents_config["researcher"], llm=llm)

    @agent
    def reporting_analyst(self) -> Agent:
        """Create a reporting analyst"""
        return Agent(config=self.agents_config["reporting_analyst"], llm=llm)

    @task
    def research_task(self) -> Task:
        """Research task implementation"""
        return Task(
            description="Conduct research on the given topic with provided context",
            agent=self.researcher(),
            expected_output="A comprehensive research report containing detailed findings, analysis, and insights on the given topic.",
        )

    @task
    def reporting_task(self) -> Task:
        """Reporting task implementation"""
        return Task(
            description="Generate analysis report based on research findings",
            agent=self.reporting_analyst(),
            expected_output="A well-structured analysis report summarizing key findings, recommendations, and actionable insights.",
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Research Crew"""
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)


class DynamicResearchFlow(Flow[DynamicResearchState]):
    """动态研究流程的实现"""

    @start()
    def initialize_research(self):
        """初始化研究参数"""
        print("Initializing research parameters")
        self.state.topic = choice(RESEARCH_TOPICS)
        self.state.extra_context = {
            "background_info": f"This is a research project about {self.state.topic}",
            "target_audience": "Technical experts and decision makers",
        }
        self.state.analysis_requirements = [
            "Compare with existing solutions",
            "Identify potential challenges",
            "Suggest future improvements",
        ]
        print(f"Selected topic: {self.state.topic}")

    @listen(initialize_research)
    def execute_research(self):
        """执行研究任务"""
        print("Executing research task")

        # 使用CrewBase模式执行研究
        research_crew = ResearchCrew()
        research_result = research_crew.crew().kickoff(
            inputs={
                "topic": self.state.topic,
                "extra_context": self.state.extra_context,
                "additional_context": "Focus on latest developments and practical applications",
                "custom_output_format": "Include technical details and implementation considerations",
            }
        )

        self.state.research_result = research_result.raw
        print("Research completed")

    @listen(execute_research)
    def generate_report(self):
        """生成研究报告"""
        print("Generating research report")

        # 使用CrewBase模式生成报告
        research_crew = ResearchCrew()
        report_result = research_crew.crew().kickoff(
            inputs={
                "topic": self.state.topic,
                "extra_context": self.state.extra_context,
                "analysis_requirements": self.state.analysis_requirements,
            }
        )

        self.state.report_result = report_result.raw
        print("Report generated")

    @listen(generate_report)
    def save_results(self):
        """保存研究结果和报告"""
        print("Saving results")
        with open(f"research_{self.state.topic.lower().replace(' ', '_')}.txt", "w") as f:
            f.write(f"Research Topic: {self.state.topic}\n")
            f.write("=" * 50 + "\n")
            f.write("Research Results:\n")
            f.write(self.state.research_result)
            f.write("\n" + "=" * 50 + "\n")
            f.write("Analysis Report:\n")
            f.write(self.state.report_result)
        print("Results saved")


def kickoff():
    """启动研究流程"""
    research_flow = DynamicResearchFlow()
    research_flow.kickoff()


def plot():
    """绘制流程图"""
    research_flow = DynamicResearchFlow()
    research_flow.plot()


if __name__ == "__main__":
    kickoff()
