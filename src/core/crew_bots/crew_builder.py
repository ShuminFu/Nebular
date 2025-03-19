import os
import sys

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(project_root)

from crewai import Agent, Task, Crew, Process
import dotenv

dotenv.load_dotenv("src/crewai_ext/config/.env")
from src.crewai_ext.config.llm_setup import llm
from crewai_tools import CodeInterpreterTool

# 使用相对路径
dockerfile_rel_path = "src/crewai_ext/config/dockers/FE.Dockerfile"
user_dockerfile_path = os.path.join(project_root, dockerfile_rel_path)
if not os.path.exists(user_dockerfile_path):
    raise FileNotFoundError(f"Dockerfile not found in {user_dockerfile_path}")

# Initialize the tool
code_interpreter = CodeInterpreterTool(
    user_dockerfile_path=user_dockerfile_path,
)

# Define an agent that focuses on Vue2 project compilation
programmer_agent = Agent(
    role="Vue2 Build Engineer",
    goal="Compile Vue2 projects and analyze the output structure using python code, given a vue2 project docker container",
    backstory="An expert Vue2 developer specialized in build processes and project structure optimization.",
    tools=[code_interpreter],
    verbose=True,
    llm=llm,
)

# Task to compile the Vue2 project and return file structure
coding_task = Task(
    description="""
    Using the Docker container configured with FE.Dockerfile:
    1. Compile the Vue2 project located at /workspace/my-vue2-project or /app/project/my-vue2-project
    2. Execute the build process using 'yarn build' or 'npm run build'
    3. After compilation, list and return the complete file structure of the output in the dist directory
    4. Analyze the compiled assets including JS, CSS, and HTML files
    5. Provide a detailed summary of the build output and file structure
    
    The Dockerfile has been configured to automatically display the compiled file structure.
    """,
    expected_output="A detailed file structure of the compiled Vue2 project, including all generated files in the dist directory and their purpose.",
    agent=programmer_agent,
)

# Create and run the crew
crew = Crew(
    agents=[programmer_agent],
    tasks=[coding_task],
    verbose=True,
    process=Process.sequential,
)
result = crew.kickoff()
