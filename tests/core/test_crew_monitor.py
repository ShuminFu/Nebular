import pytest
import unittest.mock as mock
from uuid import UUID
from src.core.entrypoints.crew_manager_main import CrewMonitor
from src.opera_service.signalr_client.opera_signalr_client import OperaCreatedArgs
from src.crewai_ext.tools.opera_api.staff_api_tool import StaffTool


class TestCrewMonitor:
    @pytest.fixture
    def monitor(self):
        """创建测试用的CrewMonitor实例"""
        with mock.patch("src.core.entrypoints.crew_manager_main.OperaSignalRClient"):
            with mock.patch("src.core.entrypoints.crew_manager_main.BotTool") as mock_bot_tool_class:
                with mock.patch("src.core.entrypoints.crew_manager_main.StaffTool") as mock_staff_tool_class:
                    with mock.patch("src.core.entrypoints.crew_manager_main.ApiResponseParser"):
                        # 创建Mock实例
                        mock_bot_tool = mock.MagicMock()
                        mock_staff_tool = mock.MagicMock()

                        # 配置Mock类返回Mock实例
                        mock_bot_tool_class.return_value = mock_bot_tool
                        mock_staff_tool_class.return_value = mock_staff_tool

                        monitor = CrewMonitor()
                        # 模拟已初始化的状态
                        monitor.managed_bots = set()
                        monitor.processes = {}
                        return monitor

    @pytest.mark.asyncio
    async def test_init_existing_bots(self, monitor: CrewMonitor):
        """测试初始化现有Bot的功能"""
        # 增加MANAGER_ROLE_FILTER常量的模拟，确保与代码匹配
        with mock.patch("src.core.entrypoints.crew_manager_main.MANAGER_ROLE_FILTER", "CrewManager"):
            # 模拟BotTool.run返回值
            monitor.bot_tool.run.return_value = "mock_result"
            monitor.bot_tool._run.return_value = "mock_result"

            # 模拟parser.parse_response返回值
            monitor.parser.parse_response.return_value = (
                200,
                [
                    {"id": "bot1", "name": "测试Bot1", "isActive": False, "defaultRoles": "CrewManager"},
                    {"id": "bot2", "name": "测试Bot2", "isActive": False, "defaultRoles": "CrewManager"},
                    {"id": "bot3", "name": "其他Bot", "isActive": False, "defaultRoles": "Agent"},  # 不符合条件
                ],
            )

            # 模拟_start_bot_manager方法
            with mock.patch.object(monitor, "_start_bot_manager") as mock_start:
                await monitor._init_existing_bots()

                # 验证只为符合条件的Bot启动了进程
                assert mock_start.call_count == 2
                mock_start.assert_any_call("bot1", "测试Bot1")
                mock_start.assert_any_call("bot2", "测试Bot2")

    @pytest.mark.asyncio
    async def test_on_opera_created_no_existing_bot_register_existing(self, monitor: CrewMonitor):
        """测试收到Opera创建事件，Opera没有符合条件的crew_manager_bots作为staff时使用现有Bot注册"""
        # 模拟MANAGER_ROLE_FILTER常量
        with mock.patch("src.core.entrypoints.crew_manager_main.MANAGER_ROLE_FILTER", "CrewManager"):
            # 模拟 StaffForCreation
            with mock.patch("src.core.entrypoints.crew_manager_main.StaffForCreation") as mock_staff_creation:
                # 配置 mock_staff_creation 返回一个有效的模拟对象
                mock_staff_obj = mock.MagicMock()
                mock_staff_creation.return_value = mock_staff_obj

                # 创建测试用Opera事件
                opera_args = OperaCreatedArgs(
                    opera_id=UUID("12345678-1234-5678-1234-567812345678"),
                    parent_id=None,
                    name="测试Opera",
                    description="测试描述",
                    database_name="test_db",
                )

                # 模拟获取Opera的staff信息 - 返回空列表，表示没有符合条件的staff
                monitor.staff_tool.run.return_value = "mock_staff_result"
                monitor.bot_tool.run.return_value = "mock_bot_result"
                monitor.bot_tool._run.return_value = "mock_bot_result"

                # 设置侧面效应，依次返回不同的结果
                monitor.parser.parse_response.side_effect = [
                    (200, []),  # 获取Opera的staff信息返回空列表
                    (
                        200,
                        [  # 获取所有Bot列表
                            {"id": "existing_bot_id", "name": "现有Bot", "defaultRoles": "CrewManager"},
                            {"id": "other_bot_id", "name": "其他Bot", "defaultRoles": "Agent"},
                        ],
                    ),
                    (200, {"success": True}),  # 注册Bot为staff的返回结果
                ]

                # 模拟_start_bot_manager方法
                with mock.patch.object(monitor, "_start_bot_manager") as mock_start:
                    await monitor._on_opera_created(opera_args)

                    # 验证API调用
                    assert monitor.staff_tool.run.call_count == 2
                    monitor.staff_tool.run.assert_any_call(action="get_all", opera_id=str(opera_args.opera_id))
                    monitor.staff_tool.run.assert_any_call(
                        action="create",
                        opera_id=str(opera_args.opera_id),
                        data=mock_staff_obj,
                    )

                    # 验证 StaffForCreation 被正确调用
                    mock_staff_creation.assert_called_once()
                    # 检查参数而不是精确的 UUID 类型
                    assert mock_staff_creation.call_args[1]["bot_id"] == "existing_bot_id"
                    assert mock_staff_creation.call_args[1]["name"] == "CM-现有Bot"
                    assert mock_staff_creation.call_args[1]["is_on_stage"] is True
                    assert mock_staff_creation.call_args[1]["tags"] == ""
                    assert mock_staff_creation.call_args[1]["roles"] == "CrewManager"
                    assert mock_staff_creation.call_args[1]["permissions"] == "manager"
                    assert mock_staff_creation.call_args[1]["parameter"] == "{}"

    @pytest.mark.asyncio
    async def test_on_opera_created_no_matching_existing_bot(self, monitor):
        """测试收到Opera创建事件，没有符合条件的现有Bot可用于注册的情况"""
        # 模拟MANAGER_ROLE_FILTER常量
        with mock.patch("src.core.entrypoints.crew_manager_main.MANAGER_ROLE_FILTER", "CrewManager"):
            # 创建测试用Opera事件
            opera_args = OperaCreatedArgs(
                opera_id=UUID("12345678-1234-5678-1234-567812345678"),
                parent_id=None,
                name="测试Opera",
                description="测试描述",
                database_name="test_db",
            )

            # 模拟获取Opera的staff信息和所有Bot - 都没有符合条件的
            monitor.staff_tool.run.return_value = "mock_staff_result"
            monitor.bot_tool.run.return_value = "mock_bot_result"
            monitor.bot_tool._run.return_value = "mock_bot_result"

            monitor.parser.parse_response.side_effect = [
                (200, []),  # 获取Opera的staff信息返回空列表
                (200, [{"id": "other_bot_id", "name": "其他Bot", "defaultRoles": "Agent"}]),  # 获取所有Bot列表，无符合条件的Bot
            ]

            # 模拟_start_bot_manager方法
            with mock.patch.object(monitor, "_start_bot_manager") as mock_start:
                await monitor._on_opera_created(opera_args)

                # 验证API调用
                monitor.staff_tool.run.assert_called_once_with(action="get_all", opera_id=str(opera_args.opera_id))
                monitor.bot_tool._run.assert_called_once_with(action="get_all")

                # 验证没有注册Bot为staff
                assert monitor.staff_tool.run.call_count == 1

                # 验证没有启动进程
                mock_start.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_opera_created_with_empty_roles(self, monitor):
        """测试收到Opera创建事件，Opera有staff但roles为空的情况"""
        # 模拟MANAGER_ROLE_FILTER常量
        with mock.patch("src.core.entrypoints.crew_manager_main.MANAGER_ROLE_FILTER", "CrewManager"):
            # 模拟 StaffForCreation
            with mock.patch("src.core.entrypoints.crew_manager_main.StaffForCreation") as mock_staff_creation:
                # 配置 mock_staff_creation 返回一个有效的模拟对象
                mock_staff_obj = mock.MagicMock()
                mock_staff_creation.return_value = mock_staff_obj

                # 创建测试用Opera事件
                opera_args = OperaCreatedArgs(
                    opera_id=UUID("12345678-1234-5678-1234-567812345678"),
                    parent_id=None,
                    name="测试Opera",
                    description="测试描述",
                    database_name="test_db",
                )

                # 模拟多个staff，有些roles为空
                mock_staffs = [
                    {
                        "botId": "bot1",
                        "botName": "Bot1",
                        "roles": [],  # 空角色列表
                        "defaultRoles": "Agent",
                    },
                    {
                        "botId": "bot2",
                        "botName": "Bot2",
                        # roles字段不存在
                        "defaultRoles": "Agent",
                    },
                    {
                        "botId": "bot3",
                        "botName": "Bot3",
                        "roles": None,  # roles为None
                        "defaultRoles": "Agent",
                    },
                ]

                # 重置mock对象
                monitor.bot_tool.run.reset_mock()
                monitor.staff_tool.run.reset_mock()
                monitor.parser.parse_response.reset_mock()

                # 设置返回值
                monitor.staff_tool.run.return_value = "mock_staff_result"
                monitor.bot_tool.run.return_value = "mock_bot_result"
                monitor.bot_tool._run.return_value = "mock_bot_result"
                monitor.parser.parse_response.side_effect = [
                    (200, mock_staffs),  # 获取Opera的staff信息
                    (200, [{"id": "existing_bot_id", "name": "现有Bot", "defaultRoles": "CrewManager"}]),  # 获取所有Bot列表
                    (200, {"success": True}),  # 注册Bot为staff的返回结果
                ]

                # 模拟_start_bot_manager方法
                with mock.patch.object(monitor, "_start_bot_manager") as mock_start:
                    await monitor._on_opera_created(opera_args)

                    # 验证API调用 - 应该调用获取staff、获取所有Bot和注册Bot为staff
                    assert monitor.staff_tool.run.call_count == 2
                    monitor.staff_tool.run.assert_any_call(action="get_all", opera_id=str(opera_args.opera_id))
                    monitor.staff_tool.run.assert_any_call(
                        action="create",
                        opera_id=str(opera_args.opera_id),
                        data=mock_staff_obj,
                    )

                    # 验证 StaffForCreation 被正确调用
                    mock_staff_creation.assert_called_once()
                    # 检查参数而不是精确的 UUID 类型
                    assert mock_staff_creation.call_args[1]["bot_id"] == "existing_bot_id"
                    assert mock_staff_creation.call_args[1]["name"] == "CM-现有Bot"
                    assert mock_staff_creation.call_args[1]["is_on_stage"] is True
                    assert mock_staff_creation.call_args[1]["tags"] == ""
                    assert mock_staff_creation.call_args[1]["roles"] == "CrewManager"
                    assert mock_staff_creation.call_args[1]["permissions"] == "manager"
                    assert mock_staff_creation.call_args[1]["parameter"] == "{}"

    @pytest.mark.asyncio
    async def test_on_opera_created_existing_bot(self, monitor):
        """测试收到Opera创建事件，Opera已有符合条件的crew_manager_bots作为staff的情况"""
        # 模拟MANAGER_ROLE_FILTER常量
        with mock.patch("src.core.entrypoints.crew_manager_main.MANAGER_ROLE_FILTER", "CrewManager"):
            # 创建测试用Opera事件
            opera_args = OperaCreatedArgs(
                opera_id=UUID("12345678-1234-5678-1234-567812345678"),
                parent_id=None,
                name="测试Opera",
                description="测试描述",
                database_name="test_db",
            )

            # 创建mock返回值
            mock_staff = {
                "botId": "existing_bot",
                "botName": "前端-Bot",  # 包含MANAGER_ROLE_FILTER
                "roles": ["CrewManager"],  # 添加roles字段，包含CrewManager角色
                "defaultRoles": "CrewManager",  # 添加defaultRoles字段
            }

            # 重置mock对象，避免之前的调用影响
            monitor.bot_tool.run.reset_mock()
            monitor.staff_tool.run.reset_mock()
            monitor.parser.parse_response.reset_mock()

            # 设置单一的返回值（不是side_effect）
            monitor.staff_tool.run.return_value = "mock_result"
            monitor.parser.parse_response.return_value = (200, [mock_staff])

            # 模拟_start_bot_manager方法
            with mock.patch.object(monitor, "_start_bot_manager") as mock_start:
                await monitor._on_opera_created(opera_args)

                # 验证API调用
                assert monitor.staff_tool.run.call_count == 1
                monitor.staff_tool.run.assert_called_once_with(action="get_all", opera_id=str(opera_args.opera_id))

                # 验证为现有Bot启动了进程，而不是创建新Bot
                mock_start.assert_called_once_with("existing_bot", "前端-Bot")

    @pytest.mark.asyncio
    async def test_on_opera_created_with_existing_managed_bot(self, monitor):
        """测试收到Opera创建事件，Opera已有符合条件的且已被管理的crew_manager_bots作为staff的情况"""
        # 模拟MANAGER_ROLE_FILTER常量
        with mock.patch("src.core.entrypoints.crew_manager_main.MANAGER_ROLE_FILTER", "CrewManager"):
            # 创建测试用Opera事件
            opera_args = OperaCreatedArgs(
                opera_id=UUID("12345678-1234-5678-1234-567812345678"),
                parent_id=None,
                name="测试Opera",
                description="测试描述",
                database_name="test_db",
            )

            # 添加一个已管理的Bot
            existing_bot_id = "existing_bot"
            monitor.managed_bots.add(existing_bot_id)

            # 模拟一个符合条件的staff，且已在managed_bots中
            mock_staff = {
                "botId": existing_bot_id,
                "botName": "前端-Bot",  # 包含MANAGER_ROLE_FILTER
                "roles": ["CrewManager"],  # 添加roles字段，包含CrewManager角色
                "defaultRoles": "CrewManager",  # 添加defaultRoles字段
            }

            # 重置mock对象
            monitor.bot_tool.run.reset_mock()
            monitor.staff_tool.run.reset_mock()
            monitor.parser.parse_response.reset_mock()

            # 设置返回值
            monitor.staff_tool.run.return_value = "mock_result"
            monitor.parser.parse_response.return_value = (200, [mock_staff])

            # 模拟_start_bot_manager方法
            with mock.patch.object(monitor, "_start_bot_manager") as mock_start:
                await monitor._on_opera_created(opera_args)

                # 验证API调用
                assert monitor.staff_tool.run.call_count == 1
                monitor.staff_tool.run.assert_called_once_with(action="get_all", opera_id=str(opera_args.opera_id))

                # 验证没有为已管理的Bot再次启动进程
                mock_start.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_opera_created_api_error(self, monitor):
        """测试当API调用失败时的情况"""
        # 模拟MANAGER_ROLE_FILTER常量
        with mock.patch("src.core.entrypoints.crew_manager_main.MANAGER_ROLE_FILTER", "CrewManager"):
            # 创建测试用Opera事件
            opera_args = OperaCreatedArgs(
                opera_id=UUID("12345678-1234-5678-1234-567812345678"),
                parent_id=None,
                name="测试Opera",
                description="测试描述",
                database_name="test_db",
            )

            # 模拟获取Opera的staff信息API调用失败
            monitor.staff_tool.run.return_value = "mock_result"
            monitor.parser.parse_response.return_value = (500, None)  # 返回错误状态码

            # 模拟_start_bot_manager方法
            with mock.patch.object(monitor, "_start_bot_manager") as mock_start:
                await monitor._on_opera_created(opera_args)

                # 验证API调用
                monitor.staff_tool.run.assert_called_once_with(action="get_all", opera_id=str(opera_args.opera_id))

                # 验证没有创建新Bot或启动进程
                mock_start.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_bot_manager_new_bot(self, monitor):
        """测试为新Bot启动进程"""
        # 模拟multiprocessing.Process
        with mock.patch("multiprocessing.Process") as mock_process:
            process_instance = mock_process.return_value

            await monitor._start_bot_manager("test_bot", "测试Bot")

            # 验证创建了新进程
            mock_process.assert_called_once()
            process_instance.start.assert_called_once()

            # 验证更新了状态
            assert "test_bot" in monitor.managed_bots
            assert "test_bot" in monitor.processes

    @pytest.mark.asyncio
    async def test_start_bot_manager_already_managed(self, monitor: CrewMonitor):
        """测试尝试为已管理的Bot启动进程"""
        # 预设已管理的Bot
        monitor.managed_bots.add("test_bot")

        # 模拟multiprocessing.Process
        with mock.patch("multiprocessing.Process") as mock_process:
            await monitor._start_bot_manager("test_bot", "测试Bot")

            # 验证没有创建新进程
            mock_process.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_bot_manager_process_exists_alive(self, monitor: CrewMonitor):
        """测试当进程已存在且活跃时的处理"""
        # 创建模拟进程
        mock_process = mock.MagicMock()
        mock_process.is_alive.return_value = True

        # 预设进程但不在managed_bots中
        monitor.processes["test_bot"] = mock_process

        # 模拟multiprocessing.Process
        with mock.patch("multiprocessing.Process") as mock_process_class:
            await monitor._start_bot_manager("test_bot", "测试Bot")

            # 验证没有创建新进程，只更新了记录
            mock_process_class.assert_not_called()
            assert "test_bot" in monitor.managed_bots

    @pytest.mark.asyncio
    async def test_start_bot_manager_process_exists_dead(self, monitor: CrewMonitor):
        """测试当进程已存在但已停止时的处理"""
        # 创建模拟进程
        mock_process = mock.MagicMock()
        mock_process.is_alive.return_value = False

        # 预设进程但不在managed_bots中
        monitor.processes["test_bot"] = mock_process

        # 模拟multiprocessing.Process
        with mock.patch("multiprocessing.Process") as mock_process_class:
            new_process = mock_process_class.return_value

            await monitor._start_bot_manager("test_bot", "测试Bot")

            # 验证终止并删除了旧进程
            mock_process.terminate.assert_called_once()
            mock_process.join.assert_called_once()

            # 验证创建了新进程
            mock_process_class.assert_called_once()
            new_process.start.assert_called_once()

            # 验证更新了状态
            assert "test_bot" in monitor.managed_bots
            assert monitor.processes["test_bot"] == new_process

    @pytest.mark.asyncio
    async def test_check_bots(self, monitor: CrewMonitor):
        """测试检查新Bot功能及检查已管理但非活跃Bot的功能"""
        # 增加MANAGER_ROLE_FILTER常量的模拟，确保与代码匹配
        with mock.patch("src.core.entrypoints.crew_manager_main.MANAGER_ROLE_FILTER", "CrewManager"):
            # 模拟当前时间
            current_time = 1000.0
            with mock.patch("asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value.time.return_value = current_time

                # 预设已管理的Bot
                monitor.managed_bots.add("bot1")
                monitor.managed_bots.add("bot2")
                monitor.managed_bots.add("bot5")  # 添加一个将在Opera中变为非活跃的Bot
                monitor.managed_bots.add("bot6")  # 添加一个处于冷却期的Bot

                # 模拟进程
                mock_process1 = mock.MagicMock()
                mock_process1.is_alive.return_value = True
                monitor.processes["bot5"] = mock_process1

                mock_process2 = mock.MagicMock()
                mock_process2.is_alive.return_value = True
                monitor.processes["bot6"] = mock_process2

                # 设置重启历史
                monitor.restart_history = {
                    "bot6": current_time - 30  # 设置为30秒前重启，应该在冷却期内
                }
                # 设置冷却时间为60秒
                monitor.restart_cooldown = 60

                # 模拟BotTool.run返回值
                monitor.bot_tool.run.return_value = "mock_result"
                monitor.bot_tool._run.return_value = "mock_result"

                # 模拟parser.parse_response返回值 - 包含新的符合条件的Bot和已管理但变为非活跃的Bot
                monitor.parser.parse_response.return_value = (
                    200,
                    [
                        {"id": "bot1", "name": "测试Bot1", "isActive": True, "defaultRoles": "CrewManager"},  # 已管理且活跃
                        {"id": "bot2", "name": "测试Bot2", "isActive": True, "defaultRoles": "CrewManager"},  # 已管理且活跃
                        {"id": "bot3", "name": "新Bot", "isActive": False, "defaultRoles": "CrewManager"},  # 新的符合条件Bot
                        {"id": "bot4", "name": "其他Bot", "isActive": False, "defaultRoles": "Agent"},  # 不符合条件
                        {
                            "id": "bot5",
                            "name": "已变非活跃",
                            "isActive": False,
                            "defaultRoles": "CrewManager",
                        },  # 已管理但变为非活跃，未在冷却期
                        {
                            "id": "bot6",
                            "name": "冷却中",
                            "isActive": False,
                            "defaultRoles": "CrewManager",
                        },  # 已管理但变为非活跃，在冷却期内
                    ],
                )

                # 模拟_start_bot_manager方法
                with mock.patch.object(monitor, "_start_bot_manager") as mock_start:
                    # 添加调试日志模拟
                    with mock.patch.object(monitor.log, "info") as mock_info:
                        await monitor._check_bots()

                        # 验证调用了_start_bot_manager两次:
                        # 1. 为新的符合条件的Bot启动进程
                        # 2. 为已管理但变为非活跃的Bot（未在冷却期）重新启动进程
                        assert mock_start.call_count == 2

                        # 验证为新的符合条件的Bot启动了进程
                        mock_start.assert_any_call("bot3", "新Bot")

                        # 验证为已管理但变为非活跃的Bot（未在冷却期）重新启动了进程
                        mock_start.assert_any_call("bot5", "已变非活跃")

                        # 验证已经从管理列表中移除了变为非活跃的Bot（在重新启动前）
                        assert "bot5" not in monitor.managed_bots

                        # 验证终止了已存在的进程
                        mock_process1.terminate.assert_called_once()
                        mock_process1.join.assert_called_once()
                        assert "bot5" not in monitor.processes

                        # 验证处于冷却期的Bot没有被重启
                        assert not mock_process2.terminate.called
                        assert "bot6" in monitor.managed_bots

                        # 验证记录了冷却期内的Bot的日志
                        assert mock_info.call_count >= 1

    @pytest.mark.asyncio
    async def test_check_bots_deleted_bots(self, monitor: CrewMonitor):
        """测试检查已被删除的Bot功能"""
        # 增加MANAGER_ROLE_FILTER常量的模拟，确保与代码匹配
        with mock.patch("src.core.entrypoints.crew_manager_main.MANAGER_ROLE_FILTER", "CrewManager"):
            # 模拟当前时间
            current_time = 1000.0
            with mock.patch("asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value.time.return_value = current_time

                # 预设已管理的Bot，其中bot7和bot8将被模拟为已删除
                monitor.managed_bots.add("bot1")  # 存在的Bot
                monitor.managed_bots.add("bot7")  # 已删除的Bot
                monitor.managed_bots.add("bot8")  # 已删除的Bot

                # 模拟进程
                mock_process1 = mock.MagicMock()
                mock_process1.is_alive.return_value = True
                monitor.processes["bot1"] = mock_process1

                mock_process2 = mock.MagicMock()
                mock_process2.is_alive.return_value = True
                monitor.processes["bot7"] = mock_process2

                mock_process3 = mock.MagicMock()
                mock_process3.is_alive.return_value = True
                monitor.processes["bot8"] = mock_process3

                # 设置重启历史
                monitor.restart_history = {"bot1": current_time - 100, "bot7": current_time - 200, "bot8": current_time - 300}

                # 模拟BotTool._run返回值
                monitor.bot_tool._run.return_value = "mock_result"

                # 模拟parser.parse_response返回值 - 只包含bot1，不包含bot7和bot8（模拟它们被删除）
                monitor.parser.parse_response.return_value = (
                    200,
                    [
                        {"id": "bot1", "name": "测试Bot1", "isActive": True, "defaultRoles": "CrewManager"},  # 存在的Bot
                        {"id": "bot2", "name": "其他Bot", "isActive": True, "defaultRoles": "Agent"},  # 其他Bot
                    ],
                )

                # 添加调试日志模拟
                with mock.patch.object(monitor.log, "info") as mock_info:
                    await monitor._check_bots()

                    # 验证被删除的Bot已从管理列表中移除
                    assert "bot7" not in monitor.managed_bots
                    assert "bot8" not in monitor.managed_bots
                    assert "bot1" in monitor.managed_bots  # 确保存在的Bot保留在列表中

                    # 验证被删除Bot的进程被终止
                    mock_process2.terminate.assert_called_once()
                    mock_process2.join.assert_called_once()
                    mock_process3.terminate.assert_called_once()
                    mock_process3.join.assert_called_once()
                    assert not mock_process1.terminate.called  # 确保存在的Bot进程未被终止

                    # 验证被删除Bot的进程被从processes字典中移除
                    assert "bot7" not in monitor.processes
                    assert "bot8" not in monitor.processes
                    assert "bot1" in monitor.processes

                    # 验证被删除Bot的重启历史被清理
                    assert "bot7" not in monitor.restart_history
                    assert "bot8" not in monitor.restart_history
                    assert "bot1" in monitor.restart_history

                    # 验证记录了删除Bot的日志
                    # 至少应该有一条包含"发现2个已被删除的Bot"的日志
                    found_deletion_log = False
                    for call in mock_info.call_args_list:
                        log_message = call[0][0]
                        if "发现2个已被删除的Bot" in log_message:
                            found_deletion_log = True
                            break
                    assert found_deletion_log, "没有找到包含已删除Bot数量的日志"

    @pytest.mark.asyncio
    async def test_check_bots_no_inactive_managed_bots(self, monitor):
        """测试当没有已管理但变为非活跃的Bot时的情况"""
        # 增加MANAGER_ROLE_FILTER常量的模拟，确保与代码匹配
        with mock.patch("src.core.entrypoints.crew_manager_main.MANAGER_ROLE_FILTER", "CrewManager"):
            # 模拟当前时间
            current_time = 1000.0
            with mock.patch("asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value.time.return_value = current_time

                # 预设已管理的Bot
                monitor.managed_bots.add("bot1")
                monitor.managed_bots.add("bot2")

                # 模拟BotTool.run返回值
                monitor.bot_tool.run.return_value = "mock_result"
                monitor.bot_tool._run.return_value = "mock_result"

                # 模拟parser.parse_response返回值 - 所有已管理的Bot都是活跃的
                monitor.parser.parse_response.return_value = (
                    200,
                    [
                        {"id": "bot1", "name": "测试Bot1", "isActive": True, "defaultRoles": "CrewManager"},  # 已管理且活跃
                        {"id": "bot2", "name": "测试Bot2", "isActive": True, "defaultRoles": "CrewManager"},  # 已管理且活跃
                        {"id": "bot3", "name": "新Bot", "isActive": False, "defaultRoles": "CrewManager"},  # 新的符合条件Bot
                        {"id": "bot4", "name": "其他Bot", "isActive": False, "defaultRoles": "Agent"},  # 不符合条件
                    ],
                )

                # 模拟_start_bot_manager方法
                with mock.patch.object(monitor, "_start_bot_manager") as mock_start:
                    await monitor._check_bots()

                    # 验证只为新的符合条件的Bot启动了进程
                    mock_start.assert_called_once_with("bot3", "新Bot")

                    # 验证已管理的Bot仍在管理列表中
                    assert "bot1" in monitor.managed_bots
                    assert "bot2" in monitor.managed_bots

    @pytest.mark.asyncio
    async def test_check_bots_cooldown_period(self, monitor: CrewMonitor):
        """测试Bot冷却期功能"""
        # 增加MANAGER_ROLE_FILTER常量的模拟，确保与代码匹配
        with mock.patch("src.core.entrypoints.crew_manager_main.MANAGER_ROLE_FILTER", "CrewManager"):
            # 模拟当前时间
            current_time = 1000.0
            with mock.patch("asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value.time.return_value = current_time

                # 预设3个已管理的Bot
                monitor.managed_bots.add("bot1")  # 活跃Bot
                monitor.managed_bots.add("bot2")  # 非活跃Bot，刚重启（在冷却期内）
                monitor.managed_bots.add("bot3")  # 非活跃Bot，重启时间已超过冷却期

                # 设置重启历史
                monitor.restart_history = {
                    "bot2": current_time - 30,  # 30秒前重启，在冷却期内
                    "bot3": current_time - 120,  # 120秒前重启，已超过冷却期
                }
                # 设置冷却时间为60秒
                monitor.restart_cooldown = 60

                # 模拟进程
                mock_process1 = mock.MagicMock()
                mock_process1.is_alive.return_value = True
                monitor.processes["bot1"] = mock_process1

                mock_process2 = mock.MagicMock()
                mock_process2.is_alive.return_value = True
                monitor.processes["bot2"] = mock_process2

                mock_process3 = mock.MagicMock()
                mock_process3.is_alive.return_value = True
                monitor.processes["bot3"] = mock_process3

                # 模拟BotTool.run返回值
                monitor.bot_tool.run.return_value = "mock_result"
                monitor.bot_tool._run.return_value = "mock_result"

                # 模拟parser.parse_response返回值
                monitor.parser.parse_response.return_value = (
                    200,
                    [
                        {"id": "bot1", "name": "测试Bot1", "isActive": True, "defaultRoles": "CrewManager"},  # 已管理且活跃
                        {
                            "id": "bot2",
                            "name": "冷却中",
                            "isActive": False,
                            "defaultRoles": "CrewManager",
                        },  # 已管理但非活跃，在冷却期内
                        {
                            "id": "bot3",
                            "name": "可重启",
                            "isActive": False,
                            "defaultRoles": "CrewManager",
                        },  # 已管理但非活跃，已超过冷却期
                        {"id": "bot4", "name": "新Bot", "isActive": False, "defaultRoles": "CrewManager"},  # 新的符合条件Bot
                    ],
                )

                # 模拟_start_bot_manager方法
                with mock.patch.object(monitor, "_start_bot_manager") as mock_start:
                    # 添加调试日志模拟
                    with mock.patch.object(monitor.log, "info") as mock_info:
                        await monitor._check_bots()

                        # 验证调用了_start_bot_manager两次:
                        # 1. 为新的符合条件的Bot启动进程
                        # 2. 为已超过冷却期的非活跃Bot重新启动进程
                        assert mock_start.call_count == 2
                        mock_start.assert_any_call("bot4", "新Bot")
                        mock_start.assert_any_call("bot3", "可重启")

                        # 验证bot3被移除并且其进程被终止
                        assert "bot3" not in monitor.managed_bots
                        mock_process3.terminate.assert_called_once()
                        mock_process3.join.assert_called_once()

                        # 验证在冷却期内的bot2没有被重启
                        assert "bot2" in monitor.managed_bots
                        assert not mock_process2.terminate.called

                        # 验证记录了冷却期内的Bot的日志
                        assert mock_info.call_count >= 1

    @pytest.mark.asyncio
    async def test_periodic_check(self, monitor: CrewMonitor):
        """测试定期检查功能"""
        # 模拟_check_bots方法
        with mock.patch.object(monitor, "_check_bots") as mock_check:
            # 模拟asyncio.sleep，在第二次调用时抛出异常以中断循环
            with mock.patch("asyncio.sleep", side_effect=[None, Exception("Stop test")]):
                try:
                    await monitor._periodic_check(interval=1)  # 设置较短的间隔以加速测试
                except Exception as e:
                    if str(e) != "Stop test":
                        raise  # 如果是其他异常则重新抛出

                # 验证调用了检查方法(由于循环会在第二次sleep时抛出异常,所以会调用两次check_bots)
                assert mock_check.call_count == 2

    @pytest.mark.asyncio
    async def test_on_opera_created_with_mixed_role_staffs(self, monitor):
        """测试收到Opera创建事件，Opera有多个staff但只有部分具有CrewManager角色的情况"""
        # 模拟MANAGER_ROLE_FILTER常量
        with mock.patch("src.core.entrypoints.crew_manager_main.MANAGER_ROLE_FILTER", "CrewManager"):
            # 创建测试用Opera事件
            opera_args = OperaCreatedArgs(
                opera_id=UUID("12345678-1234-5678-1234-567812345678"),
                parent_id=None,
                name="测试Opera",
                description="测试描述",
                database_name="test_db",
            )

            # 模拟多个staff，其中有两个具有CrewManager角色，一个没有
            mock_staffs = [
                {
                    "botId": "bot1",
                    "botName": "Bot1",
                    "roles": ["Agent"],  # 不是CrewManager角色
                    "defaultRoles": "Agent",
                },
                {
                    "botId": "bot2",
                    "botName": "Bot2",
                    "roles": ["CrewManager"],  # 具有CrewManager角色
                    "defaultRoles": "CrewManager",
                },
                {
                    "botId": "bot3",
                    "botName": "Bot3",
                    "roles": ["Agent", "CrewManager"],  # 具有CrewManager角色，名称不符合过滤条件但仍会被启动
                    "defaultRoles": "CrewManager",
                },
            ]

            # 重置mock对象
            monitor.bot_tool.run.reset_mock()
            monitor.staff_tool.run.reset_mock()
            monitor.parser.parse_response.reset_mock()

            # 设置返回值
            monitor.staff_tool.run.return_value = "mock_result"
            monitor.parser.parse_response.return_value = (200, mock_staffs)

            # 模拟_start_bot_manager方法
            with mock.patch.object(monitor, "_start_bot_manager") as mock_start:
                await monitor._on_opera_created(opera_args)

                # 验证API调用
                assert monitor.staff_tool.run.call_count == 1
                monitor.staff_tool.run.assert_called_once_with(action="get_all", opera_id=str(opera_args.opera_id))

                # 验证所有具有CrewManager角色的Bot都被启动，无论名称是否符合过滤条件
                assert mock_start.call_count == 2
                mock_start.assert_any_call("bot2", "Bot2")
                mock_start.assert_any_call("bot3", "Bot3")
