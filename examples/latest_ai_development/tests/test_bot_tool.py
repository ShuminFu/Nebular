from crewai import Agent, Task, Crew, LLM
from examples.latest_ai_development.tools.bot_api_tool import (
    GetAllBotsTool,
    GetBotByIdTool,
    CreateBotTool,
    UpdateBotTool,
    DeleteBotTool
)
import asyncio

llm_oneapi = LLM(
    model="gpt-4o",
    api_key="sk-LiZdw3jCJJ4UYver9e86625c0c6043B69820DfE3B99bA736",
    base_url="http://10.1.11.55:3000/v1"
)

async def main():
    # 创建所有工具实例
    tools = [
        GetAllBotsTool(),
        GetBotByIdTool(),
        CreateBotTool(),
        UpdateBotTool(),
        DeleteBotTool()
    ]

    # 创建一个Bot管理员Agent
    bot_manager = Agent(
        role='Bot管理员',
        goal='测试Bot API的所有功能',
        backstory="""你是一个系统管理员，负责测试Bot API的各项功能。
        你需要按顺序执行：创建Bot、查询Bot、更新Bot、最后删除Bot，
        并记录每一步的结果。""",
        tools=tools,
        verbose=True,
        llm=llm_oneapi
    )

    # 创建测试任务
    test_tasks = [
        Task(
            description="""执行以下Bot API测试流程：
            1. 创建一个新的测试Bot，名称为'TestBot'
            2. 获取所有Bot列表，确认新创建的Bot存在
            3. 使用Bot ID获取具体信息
            4. 更新Bot的描述
            5. 最后删除这个Bot

            在每一步操作后，请报告执行结果。
            如果遇到错误，请详细说明错误信息。
            """,
            agent=bot_manager,
            expected_output="在每一步操作后，请报告执行结果。如果遇到错误，请详细说明错误信息."
        )
    ]

    # 创建Crew并执行任务
    crew = Crew(
        agents=[bot_manager],
        tasks=test_tasks,
        verbose=True
    )

    result = crew.kickoff()
    print("\n最终测试结果:")
    print(result)


if __name__ == "__main__":
    # 运行测试
    asyncio.run(main())