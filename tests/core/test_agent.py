import pytest
from src.core.agent import Agent, AgentState
from src.core.agent_template import AgentTemplate

@pytest.fixture
def basic_template():
    return AgentTemplate(
        prompt_config={"system_prompt": "You are a helpful assistant"},
        llm_config={"model": "gpt-4o-mini", "temperature": 0.7},
        framework_type="autogen",
        capabilities=["chat"]
    )

def test_agent_initialization(basic_template):
    agent = Agent("test_agent", basic_template)
    assert agent.name == "test_agent"
    assert agent.state == AgentState.INITIALIZED
    
def test_agent_lifecycle(basic_template):
    agent = Agent("test_agent", basic_template)
    
    # 测试启动
    assert agent.start() is True
    assert agent.state == AgentState.RUNNING
    
    # 测试通信
    response = agent.communicate("Hello")
    assert response.startswith("Echo:")
    
    # 测试停止
    assert agent.stop() is True
    assert agent.state == AgentState.STOPPED 