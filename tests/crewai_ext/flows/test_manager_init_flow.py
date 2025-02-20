import pytest
from unittest.mock import patch, AsyncMock
import yaml
import json
from src.crewai_ext.flows.manager_init_flow import ManagerInitFlow, InitState
from src.crewai_ext.crew_bases.manager_crewbase import ManagerInitCrew


@pytest.fixture
def manager_flow():
    """创建ManagerInitFlow实例"""
    return ManagerInitFlow(query="Generate a data processing crew")


@pytest.fixture
def mock_default_configs():
    """模拟默认配置"""
    default_agents = {
        "code_generator": {
            "role": "code_generator, 专业的代码生成和优化专家",
            "goal": "生成高质量、可维护的代码",
            "backstory": "作为一名经验丰富的代码生成专家，我精通各种编程语言和框架。 我注重代码的可读性、可维护性和性能，能够根据需求生成最佳实践的代码实现。 我会考虑项目的整体架构，确保生成的代码符合项目规范和最佳实践。",
        }
    }
    default_tasks = {
        "code_generation_task": {
            "description": "根据以下信息生成代码： 1. 文件路径：{file_path} 2. 文件类型：{file_type} 3. 需求描述：{requirement} 4. 项目信息：\n    - 类型：{project_type}\n    - 描述：{project_description}\n    - 框架：{frameworks}\n5. 相关文件：{resources} 6. 引用关系：{references}\n",
            "expected_output": "@file: {file_path} @description: [简要描述文件的主要功能和用途] @tags: [相关标签，如framework_xxx,feature_xxx等，用逗号分隔] @version: 1.0.0 @version_id: [UUID格式的版本ID] --- [完整的代码实现，包含： 1. 必要的导入语句 2. 类型定义（如果需要） 3. 主要功能实现 4. 错误处理 5. 导出语句（如果需要）]\n",
            "agent": "code_generator",
        },
        "chat_task": {
            "description": "根据以下对话信息生成回复： 1. 内容：{text} 要求： 1. 保持友好和专业的语气 2. 根据对话类型和标签调整回复风格 3. 如果是普通对话，给出合适的回应 4. 如果提到了其他Staff，注意回复的针对性 5. 避免过于冗长的回复 6. 保持对话的连贯性\n",
            "expected_output": "[回复内容]\n",
            "agent": "code_generator",
        },
    }
    return default_agents, default_tasks


def test_initial_state(manager_flow):
    """测试初始状态"""
    assert isinstance(manager_flow.state, InitState)
    assert manager_flow.state.validation_passed is False
    assert manager_flow.state.error_messages == {}
    assert manager_flow.state.current_step == "init"
    assert "runners" in manager_flow.state.config
    assert isinstance(manager_flow.state.config["runners"], list)


@pytest.mark.asyncio
async def test_start_flow(manager_flow, mock_default_configs):
    """测试流程初始化"""
    default_agents, default_tasks = mock_default_configs

    with patch.object(ManagerInitFlow, "_load_default_config") as mock_load:
        mock_load.side_effect = [default_agents, default_tasks]

        manager_flow.start_flow()

        assert manager_flow.state.current_step == "need_generate_configs"
        assert len(manager_flow.state.config["runners"]) == 1
        assert manager_flow.state.config["runners"][0]["agents"] == default_agents
        assert manager_flow.state.config["runners"][0]["tasks"] == default_tasks


@pytest.mark.asyncio
async def test_generate_configs(manager_flow):
    """测试配置生成"""
    # 模拟配置生成结果
    mock_config = {
        "runners": [
            {
                "agents": {
                    "code_generator": {
                        "role": "code_generator, 专业的代码生成和优化专家",
                        "goal": "生成高质量、可维护的代码",
                        "backstory": "作为一名经验丰富的代码生成专家，我精通各种编程语言和框架。 我注重代码的可读性、可维护性和性能，能够根据需求生成最佳实践的代码实现。 我会考虑项目的整体架构，确保生成的代码符合项目规范和最佳实践。",
                    }
                },
                "tasks": {
                    "code_generation_task": {
                        "description": "根据以下信息生成代码： 1. 文件路径：{file_path} 2. 文件类型：{file_type} 3. 需求描述：{requirement} 4. 项目信息：\n    - 类型：{project_type}\n    - 描述：{project_description}\n    - 框架：{frameworks}\n5. 相关文件：{resources} 6. 引用关系：{references}\n",
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
        ]
    }

    with patch.object(ManagerInitCrew, "crew") as mock_crew:
        mock_crew_instance = AsyncMock()
        mock_crew_instance.kickoff_async.return_value.raw = json.dumps(mock_config)
        mock_crew.return_value = mock_crew_instance

        await manager_flow.generate_configs()

        assert manager_flow.state.current_step == "need_validate_configs"
        assert "code_generator" in manager_flow.state.config["runners"][0]["agents"]
        assert "code_generation_task" in manager_flow.state.config["runners"][0]["tasks"]



@pytest.mark.asyncio
async def test_validate_configuration(manager_flow):
    """测试配置验证"""
    # 设置有效配置
    manager_flow.state.config = {"runners": [{"agents": {"test_agent": {}}, "tasks": {"test_task": {}}}]}

    await manager_flow.validate_configuration()

    assert manager_flow.state.current_step == "need_output_config"
    assert manager_flow.state.config["validation"]["passed"] is True
    assert not manager_flow.state.error_messages


@pytest.mark.asyncio
async def test_validate_configuration_failure(manager_flow):
    """测试配置验证失败"""
    # 设置无效配置
    manager_flow.state.config = {
        "runners": [
            {
                "agents": {},  # 缺少必要的agents配置
                "tasks": {"test_task": {}},
            }
        ]
    }

    await manager_flow.validate_configuration()

    assert manager_flow.state.current_step == "need_generate_configs"
    assert "validation" in manager_flow.state.error_messages


@pytest.mark.asyncio
async def test_output_configuration(manager_flow):
    """测试配置输出"""
    test_config = {"runners": [{"agents": {"test_agent": {}}, "tasks": {"test_task": {}}}], "validation": {"passed": True}}
    manager_flow.state.config = test_config

    result = await manager_flow.output_configuration()

    assert result == test_config


@pytest.mark.asyncio
async def test_parse_config_skeleton(manager_flow):
    """测试配置骨架解析"""
    raw_config = """
    {
        "runners": [{
            "agents": {
                "new_agent": {
                    "name": "New Agent",
                    "role": "New Role"
                }
            },
            "tasks": {
                "new_task": {
                    "name": "New Task",
                    "description": "New Description"
                }
            }
        }]
    }
    """

    # 设置初始配置
    manager_flow.state.config = {
        "runners": [
            {"agents": {"existing_agent": {"name": "Existing Agent"}}, "tasks": {"existing_task": {"name": "Existing Task"}}}
        ]
    }

    manager_flow._parse_config_skeleton(raw_config)

    # 验证新配置被合并到现有配置中
    config = manager_flow.state.config
    assert "new_agent" in config["runners"][0]["agents"]
    assert "existing_agent" in config["runners"][0]["agents"]
    assert "new_task" in config["runners"][0]["tasks"]
    assert "existing_task" in config["runners"][0]["tasks"]


@pytest.mark.asyncio
async def test_full_flow_execution(manager_flow, mock_default_configs):
    """测试完整流程执行"""
    default_agents, default_tasks = mock_default_configs

    # 模拟配置生成结果
    mock_config = {
        "runners": [
            {
                "agents": {
                    "data_processor": {
                        "name": "Data Processor",
                        "role": "Process data efficiently",
                    }
                },
                "tasks": {
                    "process_data": {
                        "name": "Process Data",
                        "description": "Process the input data",
                    }
                },
            }
        ]
    }

    with patch.object(ManagerInitFlow, "_load_default_config") as mock_load, patch.object(ManagerInitCrew, "crew") as mock_crew:
        # 模拟加载默认配置
        mock_load.side_effect = [default_agents, default_tasks]

        # 模拟crew执行
        mock_crew_instance = AsyncMock()
        mock_crew_instance.kickoff_async.return_value.raw = json.dumps(mock_config)
        mock_crew.return_value = mock_crew_instance

        # 执行完整流程
        await manager_flow.kickoff_async()

        # 验证状态转换
        assert manager_flow.state.current_step == "need_output_config"
        assert manager_flow.state.config["validation"]["passed"] is True

        # 验证配置内容
        final_config = manager_flow.state.config
        assert "data_processor" in final_config["runners"][0]["agents"]
        assert "process_data" in final_config["runners"][0]["tasks"]
