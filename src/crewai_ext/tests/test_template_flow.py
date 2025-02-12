import pytest
from ..flows.template_flow import DynamicResearchFlow, DynamicResearchState, RESEARCH_TOPICS, ResearchCrew
from unittest.mock import patch, mock_open, MagicMock
from crewai import Agent, Task


@pytest.fixture
def research_flow():
    """创建DynamicResearchFlow实例"""
    return DynamicResearchFlow()


@pytest.fixture
def research_crew():
    """创建ResearchCrew实例"""
    return ResearchCrew()


def test_initial_state():
    """测试初始状态"""
    flow = DynamicResearchFlow()
    assert isinstance(flow.state, DynamicResearchState)
    assert flow.state.topic == ""
    assert flow.state.extra_context == {}
    assert flow.state.research_result == ""
    assert flow.state.report_result == ""
    assert flow.state.analysis_requirements == []


def test_research_crew_agents(research_crew):
    """测试ResearchCrew的agents配置"""
    researcher = research_crew.researcher()
    reporting_analyst = research_crew.reporting_analyst()

    assert isinstance(researcher, Agent)
    assert isinstance(reporting_analyst, Agent)


def test_research_crew_tasks(research_crew):
    """测试ResearchCrew的tasks配置"""
    research_task = research_crew.research_task()
    reporting_task = research_crew.reporting_task()

    assert isinstance(research_task, Task)
    assert isinstance(reporting_task, Task)

    # 验证task属性
    assert research_task.description == "Conduct research on the given topic with provided context"
    assert (
        research_task.expected_output
        == "A comprehensive research report containing detailed findings, analysis, and insights on the given topic."
    )

    assert reporting_task.description == "Generate analysis report based on research findings"
    assert (
        reporting_task.expected_output
        == "A well-structured analysis report summarizing key findings, recommendations, and actionable insights."
    )


def test_research_crew_creation(research_crew):
    """测试ResearchCrew的创建"""
    crew = research_crew.crew()
    assert len(crew.agents) == 2  # 研究员和报告分析师
    assert len(crew.tasks) == 2  # 研究任务和报告任务
    assert crew.process == "sequential"
    assert crew.verbose is True


def test_initialize_research(research_flow):
    """测试研究初始化"""
    research_flow.initialize_research()

    assert research_flow.state.topic in RESEARCH_TOPICS
    assert "background_info" in research_flow.state.extra_context
    assert "target_audience" in research_flow.state.extra_context
    assert len(research_flow.state.analysis_requirements) == 3


def test_execute_research(research_flow):
    """测试研究执行"""
    with patch.object(ResearchCrew, "crew") as mock_crew:
        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.return_value.raw = "Mocked research result"
        mock_crew.return_value = mock_crew_instance

        research_flow.initialize_research()
        research_flow.execute_research()

        assert research_flow.state.research_result == "Mocked research result"
        mock_crew_instance.kickoff.assert_called_once()


def test_generate_report(research_flow):
    """测试报告生成"""
    with patch.object(ResearchCrew, "crew") as mock_crew:
        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.return_value.raw = "Mocked report result"
        mock_crew.return_value = mock_crew_instance

        research_flow.initialize_research()
        research_flow.state.research_result = "Previous research result"
        research_flow.generate_report()

        assert research_flow.state.report_result == "Mocked report result"
        mock_crew_instance.kickoff.assert_called_once()


def test_save_results(research_flow):
    """测试结果保存"""
    # 准备状态
    research_flow.initialize_research()
    research_flow.state.research_result = "Test research results"
    research_flow.state.report_result = "Test report results"

    # 模拟文件操作
    mock_file = mock_open()
    with patch("builtins.open", mock_file):
        research_flow.save_results()

    # 验证文件写入
    mock_file.assert_called_once()
    handle = mock_file()

    # 验证写入内容
    write_calls = handle.write.call_args_list
    assert any("Research Topic:" in str(call) for call in write_calls)
    assert any("Test research results" in str(call) for call in write_calls)
    assert any("Test report results" in str(call) for call in write_calls)


def test_full_flow_execution(research_flow):
    """测试完整流程执行"""
    with patch.object(ResearchCrew, "crew") as mock_crew:
        mock_crew_instance = MagicMock()
        # 模拟研究和报告生成的结果
        mock_crew_instance.kickoff.side_effect = [MagicMock(raw="Mocked research result"), MagicMock(raw="Mocked report result")]
        mock_crew.return_value = mock_crew_instance

        # 模拟文件操作
        with patch("builtins.open", mock_open()):
            research_flow.kickoff()

        # 验证状态
        assert research_flow.state.topic in RESEARCH_TOPICS
        assert research_flow.state.research_result == "Mocked research result"
        assert research_flow.state.report_result == "Mocked report result"

        # 验证crew.kickoff被调用了两次（研究和报告）
        assert mock_crew_instance.kickoff.call_count == 2


@pytest.mark.parametrize("topic", RESEARCH_TOPICS)
def test_different_topics(topic):
    """测试不同研究主题"""
    flow = DynamicResearchFlow()

    with patch.object(ResearchCrew, "crew") as mock_crew:
        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.return_value.raw = "Mocked result"
        mock_crew.return_value = mock_crew_instance

        # 强制设置特定主题
        with patch("random.choice", return_value=topic):
            flow.initialize_research()

        assert flow.state.topic == topic
        assert f"about {topic}" in flow.state.extra_context["background_info"]
