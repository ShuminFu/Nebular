import pytest
from uuid import UUID
from src.core.crew_process import CrewRunner, RunnerCodeGenerationCrew
from src.crewai_ext.crew_bases.runner_crewbase import RunnerChatCrew


@pytest.fixture
def mock_bot_id():
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def mock_parent_bot_id():
    return UUID("87654321-4321-8765-4321-876543210987")


@pytest.fixture
def sample_crew_config():
    return {
        "agents": {
            "code_generator": {
                "role": "injected_code_generator, 专业的代码生成和优化专家",
                "goal": "生成高质量、可维护的代码",
                "backstory": "作为一名经验丰富的代码生成专家，我精通各种编程语言和框架。 我注重代码的可读性、可维护性和性能，能够根据需求生成最佳实践的代码实现。 我会考虑项目的整体架构，确保生成的代码符合项目规范和最佳实践。",
            }
        },
        "tasks": {
            "code_generation_task": {
                "description": "injected 根据以下信息生成代码： 1. 文件路径：{file_path} 2. 文件类型：{file_type} 3. 需求描述：{requirement} 4. 项目信息：\n    - 类型：{project_type}\n    - 描述：{project_description}\n    - 框架：{frameworks}\n5. 相关文件：{resources} 6. 引用关系：{references}\n",
                "expected_output": "@file: {file_path} @description: [简要描述文件的主要功能和用途] @tags: [相关标签，如framework_xxx,feature_xxx等，用逗号分隔] @version: 1.0.0 @version_id: [UUID格式的版本ID] --- [完整的代码实现，包含： 1. 必要的导入语句 2. 类型定义（如果需要） 3. 主要功能实现 4. 错误处理 5. 导出语句（如果需要）]\n",
                "agent": "code_generator",
            },
            "chat_task": {
                "description": "根据以下对话信息生成回复： 1. 内容：{text} 要求： 1. 保持友好和专业的语气 2. 根据对话类型和标签调整回复风格 3. 如果是普通对话，给出合适的回应 4. 如果提到了其他Staff，注意回复的针对性 5. 避免过于冗长的回复 6. 保持对话的连贯性\n",
                "expected_output": "[回复内容]\n",
                "agent": "code_generator",
            },
        },
    }


@pytest.mark.asyncio
async def test_crew_runner_initialization():
    """测试 CrewRunner 的基本初始化"""
    bot_id = UUID("12345678-1234-5678-1234-567812345678")
    parent_bot_id = UUID("87654321-4321-8765-4321-876543210987")
    crew_config = None

    runner = CrewRunner(bot_id=bot_id, parent_bot_id=parent_bot_id, crew_config=crew_config)

    assert runner.bot_id == bot_id
    assert runner.parent_bot_id == parent_bot_id
    assert runner.crew_config is None
    assert isinstance(runner.chat_crew, RunnerChatCrew)


@pytest.mark.asyncio
async def test_crew_runner_with_dynamic_config(mock_bot_id, mock_parent_bot_id, sample_crew_config):
    """测试使用动态配置创建 CrewRunner"""
    runner = CrewRunner(bot_id=mock_bot_id, parent_bot_id=mock_parent_bot_id, crew_config=sample_crew_config)

    # 验证基本属性
    assert runner.bot_id == mock_bot_id
    assert runner.parent_bot_id == mock_parent_bot_id
    assert runner.crew_config == sample_crew_config

    # 验证动态创建的 Crew
    crew = runner.crew
    assert isinstance(crew, RunnerCodeGenerationCrew)

    # 验证动态配置是否正确应用
    assert hasattr(crew, "agents_config")
    assert hasattr(crew, "tasks_config")
    assert crew.agents_config == sample_crew_config["agents"]
    assert crew.tasks_config == sample_crew_config["tasks"]


@pytest.mark.asyncio
async def test_create_dynamic_crew(mock_bot_id, mock_parent_bot_id, sample_crew_config):
    """测试动态 Crew 的创建过程"""
    runner = CrewRunner(bot_id=mock_bot_id, parent_bot_id=mock_parent_bot_id, crew_config=sample_crew_config)

    # 使用工厂方法创建动态 Crew 类
    dynamic_crew = runner.crew

    # 验证继承关系
    assert isinstance(dynamic_crew, RunnerCodeGenerationCrew)

    # 验证配置是否正确应用
    assert dynamic_crew.agents_config == sample_crew_config["agents"]
    assert dynamic_crew.tasks_config == sample_crew_config["tasks"]

    # 验证配置内容
    assert "code_generator" in dynamic_crew.agents_config
    assert "code_generation_task" in dynamic_crew.tasks_config
    assert "chat_task" in dynamic_crew.tasks_config


@pytest.mark.asyncio
async def test_crew_runner_without_config(mock_bot_id, mock_parent_bot_id):
    """测试不使用动态配置的 CrewRunner"""
    runner = CrewRunner(bot_id=mock_bot_id, parent_bot_id=mock_parent_bot_id, crew_config=None)

    crew = runner._setup_crew()

    # 验证默认 Crew 创建
    assert isinstance(crew, RunnerCodeGenerationCrew)
    assert not hasattr(crew, "agents_config")
    assert not hasattr(crew, "tasks_config")


@pytest.mark.asyncio
async def test_crew_runner_with_invalid_config(mock_bot_id, mock_parent_bot_id):
    """测试使用无效配置创建 CrewRunner"""
    invalid_config = {
        "agents": {},  # 空的 agents 配置
        "tasks": {},  # 空的 tasks 配置
    }

    runner = CrewRunner(bot_id=mock_bot_id, parent_bot_id=mock_parent_bot_id, crew_config=invalid_config)

    crew = runner._setup_crew()

    # 验证即使配置无效也能创建基本的 Crew
    assert isinstance(crew, RunnerCodeGenerationCrew)
    assert crew.agents_config == {}
    assert crew.tasks_config == {}
