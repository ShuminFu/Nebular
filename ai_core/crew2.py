from crewai import Crew, Agent, Task
from crewai import LLM


# Check our tools documentations for more information on how to use them
# from crewai_tools import SerperDevTool
llm_oneapi = LLM(
    model="gpt-4o",
    api_key="sk-LiZdw3jCJJ4UYver9e86625c0c6043B69820DfE3B99bA736",
    base_url="http://10.1.11.55:3000/v1"
)


coding_agent = Agent(
    role="Python Data Analyst",
    goal="Analyze data and provide insights using Python",
    backstory="You are an experienced data analyst with strong Python skills.",
    allow_code_execution=True,
    llm=llm_oneapi

)

# Create a task that requires code execution
data_analysis_task = Task(
    description="Analyze the given dataset and calculate the average age of participants. Ages: {ages}",
    agent=coding_agent,
    expected_output="The average age calculated from the dataset"
)

# Create a crew and add the task
analysis_crew = Crew(
    agents=[coding_agent],
    tasks=[data_analysis_task],
    verbose=True,
    memory=False,
    respect_context_window=True  # enable by default
)

datasets = [
  { "ages": [25, 30, 35, 40, 45] },
  { "ages": [20, 25, 30, 35, 40] },
  { "ages": [30, 35, 40, 45, 50] }
]

# Execute the crew
result = analysis_crew.kickoff_for_each(inputs=datasets)

