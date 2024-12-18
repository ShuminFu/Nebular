"""
预先定义了BaseCrew进程中的两个核心Agent：
1. IntentMind: 负责对话意图分析和任务队列管理的Agent
   - 分析用户对话意图
   - 管理对话和任务队列
   - 过滤无效对话
   - 更新staff参数

2. PersonaSwitch: 负责角色切换和回复的Agent
   - 处理任务结果
   - 切换staff身份
   - 生成合适的回复
   - 更新任务状态

使用方法:
    from ai_core.configs.base_agents import create_intent_mind_agent, create_persona_switch_agent
    
    # 创建IntentMind Agent
    intent_mind = create_intent_mind_agent()
    
    # 创建PersonaSwitch Agent
    persona_switch = create_persona_switch_agent()
    
    # 可以自定义工具列表
    custom_tools = [CustomTool1(), CustomTool2()]
    custom_agent = create_intent_mind_agent(tools=custom_tools)

测试:
    直接运行此脚本进行Agent功能测试:
    python -m ai_core.configs.base_agents
"""

from crewai import Agent, Task, Crew
from typing import List
from ai_core.tools.opera_api.bot_api_tool import BotTool
from ai_core.tools.opera_api.dialogue_api_tool import DialogueTool
from ai_core.tools.opera_api.staff_api_tool import StaffTool
from ai_core.configs.config import llm

def create_intent_agent(tools: List = None) -> Agent:
    """
    创建IntentMind Agent
    负责处理对话意图识别和任务队列管理
    """
    if tools is None:
        tools = [BotTool(), DialogueTool()]
    
    return Agent(
        name="IntentMind",
        role="Dialogue Intent Analyzer",
        goal="分析对话意图并管理任务队列",
        backstory="""你是一位专业的对话意图分析专家，擅长理解用户意图并管理任务队列。
        你的主要职责包括：
        1. 检查和更新staff参数中的对话队列
        2. 检查和更新Bot defaultTags中的任务队列
        3. 准确识别对话中的意图和需求, 过滤掉无意义的对话，将有意义的对话加入到待处理消息队列中。
        4. 确保所有对话都得到适当的处理和响应
        """,
        tools=tools,
        verbose=True,
        llm=llm  
    )

def create_persona_agent(tools: List = None) -> Agent:
    """
    创建PersonaSwitch Agent
    负责处理任务结果并以对应staff身份发言
    """
    if tools is None:
        tools = [DialogueTool(), StaffTool(), BotTool()]
    
    return Agent(
        name="PersonaSwitch",
        role="Persona Manager",
        goal="处理任务结果并准确切换不同staff的角色身份来调用DialogueTool",
        backstory="""你是一位专业的角色管理专家，负责确保以正确的身份和语气进行回应。
        你的主要职责包括：
        1. 根据不同staff的特点和要求处理任务结果
        2. 以对应staff的身份和语气进行回复
        3. 任务完成后更新任务队列状态
        4. 确保回复的语气和内容符合staff的特征
        """,
        tools=tools,
        verbose=True,
        llm=llm  
    )

if __name__ == "__main__":
    import asyncio
    import sys
    from loguru import logger
    
    # 配置logger
    logger.remove()
    logger.add(sys.stdout, level="INFO")
    
    async def test_agents():
        """测试Agent的基本功能"""
        # 创建测试用的Agent实例
        intent_agent = create_intent_agent()
        persona_switch = create_persona_agent()
        
        # 创建测试用的Crew
        test_crew = Crew(
            agents=[intent_agent, persona_switch],
            tasks=[
                # 测试IntentMind的对话意图分析
                Task(
                    description="分析以下对话的意图：'我需要帮助设置我的账户'",
                    expected_output="""请提供一个详细的用户意图分析，包括：
                    1. 主要意图（账户设置帮助）
                    2. 可能的具体需求
                    3. 用户可能遇到的问题
                    4. 建议的处理优先级""",
                    agent=intent_agent
                ),
                # 测试PersonaSwitch的角色切换
                Task(
                    description="以技术支持人员的身份回复：'如何重置我的密码？'",
                    expected_output="""请提供一个专业的技术支持回复，需要包含：
                    1. 适当的问候语
                    2. 清晰的密码重置步骤说明
                    3. 可能遇到的问题及解决方案
                    4. 友好的结束语和后续支持提示""",
                    agent=persona_switch
                )
            ],
            verbose=True
        )
        
        try:
            # 运行测试任务
            result = test_crew.kickoff()
            print("\n=== 测试结果 ===")
            print(f"任务执行结果: {result}")
            return True
        except Exception as e:
            print(f"\n=== 测试失败 ===")
            print(f"错误信息: {str(e)}")
            return False
    
    # 运行测试
    logger.info("开始测试基础Agent...")
    success = asyncio.run(test_agents())
    
    if success:
        logger.success("Agent测试完成！")
    else:
        logger.error("Agent测试失败！") 