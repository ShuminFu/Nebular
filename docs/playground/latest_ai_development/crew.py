# pylint: skip-file
from crewai import Agent, Crew, Task

# Uncomment the following line to use an example of a custom tool
from crewai import LLM

# load_dotenv("configs/.env")

# Check our tools documentations for more information on how to use them
# from crewai_tools import SerperDevTool
llm_oneapi = LLM(
    model="gpt-4o",
    api_key="sk-LiZdw3jCJJ4UYver9e86625c0c6043B69820DfE3B99bA736",
    base_url="http://10.1.11.55:3000/v1"
)

from src.crewai_core.configs import llm
# @CrewBase
# class LatestAiDevelopment:
# 	"""LatestAiDevelopment crew"""
#
# 	agents_config = 'config/agents.yaml'
# 	tasks_config = 'config/tasks.yaml'
#
# 	@agent
# 	def researcher(self) -> Agent:
# 		return Agent(
# 			config=self.agents_config['researcher'],
# 			tools=[MyCustomTool()], # Example of custom tool, loaded on the beginning of file
# 			verbose=True,
# 			llm=llm_oneapi
# 		)
#
# 	@agent
# 	def reporting_analyst(self) -> Agent:
# 		return Agent(
# 			config=self.agents_config['reporting_analyst'],
# 			verbose=True,
# 			llm=llm_oneapi
# 		)
#
# 	@task
# 	def research_task(self) -> Task:
# 		return Task(
# 			config=self.tasks_config['research_task'],
# 		)
#
# 	@task
# 	def reporting_task(self) -> Task:
# 		return Task(
# 			config=self.tasks_config['reporting_task'],
# 			output_file='report.md'
# 		)
#
# 	@crew
# 	def crew(self) -> Crew:
# 		"""Creates the LatestAiDevelopment crew"""
# 		return Crew(
# 			agents=self.agents, # Automatically created by the @agent decorator
# 			tasks=self.tasks, # Automatically created by the @task decorator
# 			process=Process.sequential,
# 			verbose=True,
# 			# process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
# 		)
#

coding_agent = Agent(
    role="Python Data Analyst",
    goal="Analyze data and provide insights using Python",
    backstory="You are an experienced data analyst with strong Python skills.",
    allow_code_execution=True,
	llm=llm,
	verbose=True
)

# Create a task that requires code execution
data_analysis_task = Task(
    description="Analyze the given dataset and calculate the average age of participants.",
	expected_output="The average age of participants is 30 years.",
    agent=coding_agent
)

# Create a crew and add the task
analysis_crew = Crew(
    agents=[coding_agent],
    tasks=[data_analysis_task]
)

# Execute the crew
result = analysis_crew.kickoff()

print(result)




