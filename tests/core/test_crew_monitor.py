import pytest
import unittest.mock as mock
from uuid import UUID
from src.core.entrypoints.crew_manager_main import CrewMonitor
from src.opera_service.signalr_client.opera_signalr_client import OperaCreatedArgs


class TestCrewMonitor:
    @pytest.fixture
    def monitor(self):
        """创建测试用的CrewMonitor实例"""
        with mock.patch("src.core.entrypoints.crew_manager_main.OperaSignalRClient"):
            with mock.patch("src.core.entrypoints.crew_manager_main.BotTool"):
                with mock.patch("src.core.entrypoints.crew_manager_main.ApiResponseParser"):
                    monitor = CrewMonitor()
                    # 模拟已初始化的状态
                    monitor.managed_bots = set()
                    monitor.processes = {}
                    return monitor

    @pytest.mark.asyncio
    async def test_init_existing_bots(self, monitor):
        """测试初始化现有Bot的功能"""
        # 增加BOT_NAME_FILTER常量的模拟，确保与代码匹配
        with mock.patch("src.core.entrypoints.crew_manager_main.BOT_NAME_FILTER", "前端-"):
            # 模拟BotTool.run返回值
            monitor.bot_tool.run.return_value = "mock_result"

            # 模拟parser.parse_response返回值
            monitor.parser.parse_response.return_value = (
                200,
                [
                    {"id": "bot1", "name": "前端-测试Bot1", "isActive": False},
                    {"id": "bot2", "name": "前端-测试Bot2", "isActive": False},
                    {"id": "bot3", "name": "其他Bot", "isActive": False},  # 不符合条件
                ],
            )

            # 模拟_start_bot_manager方法
            with mock.patch.object(monitor, "_start_bot_manager") as mock_start:
                await monitor._init_existing_bots()

                # 验证只为符合条件的Bot启动了进程
                assert mock_start.call_count == 2
                mock_start.assert_any_call("bot1", "前端-测试Bot1")
                mock_start.assert_any_call("bot2", "前端-测试Bot2")

    @pytest.mark.asyncio
    async def test_on_opera_created_no_existing_bot_create_new(self, monitor):
        """测试收到Opera创建事件，Opera没有符合条件的crew_manager_bots作为staff时创建新Bot"""
        # 模拟BOT_NAME_FILTER常量
        with mock.patch("src.core.entrypoints.crew_manager_main.BOT_NAME_FILTER", "前端-"):
            # 创建测试用Opera事件
            opera_args = OperaCreatedArgs(
                opera_id=UUID("12345678-1234-5678-1234-567812345678"),
                parent_id=None,
                name="测试Opera",
                description="测试描述",
                database_name="test_db",
            )

            # 模拟获取Opera的staff信息 - 返回空列表，表示没有符合条件的staff
            monitor.bot_tool.run.return_value = "mock_result"
            monitor.parser.parse_response.side_effect = [
                (200, []),  # 获取Opera的staff信息返回空列表
                (200, {"id": "new_bot_id", "name": "前端-测试Opera"}),  # 创建新Bot返回结果
            ]

            # 模拟_start_bot_manager方法
            with mock.patch.object(monitor, "_start_bot_manager") as mock_start:
                await monitor._on_opera_created(opera_args)

                # 验证API调用
                assert monitor.bot_tool.run.call_count == 2
                monitor.bot_tool.run.assert_any_call(action="get_opera_staffs", opera_id=str(opera_args.opera_id))

                # 验证创建了新Bot并启动了进程
                mock_start.assert_called_once_with("new_bot_id", "前端-测试Opera")

    @pytest.mark.asyncio
    async def test_on_opera_created_existing_bot(self, monitor):
        """测试收到Opera创建事件，Opera已有符合条件的crew_manager_bots作为staff的情况"""
        # 模拟BOT_NAME_FILTER常量
        with mock.patch("src.core.entrypoints.crew_manager_main.BOT_NAME_FILTER", "前端-"):
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
                "botName": "前端-Bot",  # 包含BOT_NAME_FILTER
            }

            # 重置mock对象，避免之前的调用影响
            monitor.bot_tool.run.reset_mock()
            monitor.parser.parse_response.reset_mock()

            # 设置单一的返回值（不是side_effect）
            monitor.bot_tool.run.return_value = "mock_result"
            monitor.parser.parse_response.return_value = (200, [mock_staff])

            # 模拟_start_bot_manager方法
            with mock.patch.object(monitor, "_start_bot_manager") as mock_start:
                await monitor._on_opera_created(opera_args)

                # 验证API调用
                assert monitor.bot_tool.run.call_count == 1
                monitor.bot_tool.run.assert_called_once_with(action="get_opera_staffs", opera_id=str(opera_args.opera_id))

                # 验证为现有Bot启动了进程，而不是创建新Bot
                mock_start.assert_called_once_with("existing_bot", "前端-Bot")

    @pytest.mark.asyncio
    async def test_on_opera_created_with_existing_managed_bot(self, monitor):
        """测试收到Opera创建事件，Opera已有符合条件的且已被管理的crew_manager_bots作为staff的情况"""
        # 模拟BOT_NAME_FILTER常量
        with mock.patch("src.core.entrypoints.crew_manager_main.BOT_NAME_FILTER", "前端-"):
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
                "botName": "前端-Bot",  # 包含BOT_NAME_FILTER
            }

            # 重置mock对象
            monitor.bot_tool.run.reset_mock()
            monitor.parser.parse_response.reset_mock()

            # 设置返回值
            monitor.bot_tool.run.return_value = "mock_result"
            monitor.parser.parse_response.return_value = (200, [mock_staff])

            # 模拟_start_bot_manager方法
            with mock.patch.object(monitor, "_start_bot_manager") as mock_start:
                await monitor._on_opera_created(opera_args)

                # 验证API调用
                assert monitor.bot_tool.run.call_count == 1
                monitor.bot_tool.run.assert_called_once_with(action="get_opera_staffs", opera_id=str(opera_args.opera_id))

                # 验证没有为已管理的Bot再次启动进程
                mock_start.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_opera_created_api_error(self, monitor):
        """测试当API调用失败时的情况"""
        # 模拟BOT_NAME_FILTER常量
        with mock.patch("src.core.entrypoints.crew_manager_main.BOT_NAME_FILTER", "前端-"):
            # 创建测试用Opera事件
            opera_args = OperaCreatedArgs(
                opera_id=UUID("12345678-1234-5678-1234-567812345678"),
                parent_id=None,
                name="测试Opera",
                description="测试描述",
                database_name="test_db",
            )

            # 模拟获取Opera的staff信息API调用失败
            monitor.bot_tool.run.return_value = "mock_result"
            monitor.parser.parse_response.return_value = (500, None)  # 返回错误状态码

            # 模拟_start_bot_manager方法
            with mock.patch.object(monitor, "_start_bot_manager") as mock_start:
                await monitor._on_opera_created(opera_args)

                # 验证API调用
                monitor.bot_tool.run.assert_called_once_with(action="get_opera_staffs", opera_id=str(opera_args.opera_id))

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
        # 增加BOT_NAME_FILTER常量的模拟，确保与代码匹配
        with mock.patch("src.core.entrypoints.crew_manager_main.BOT_NAME_FILTER", "前端-"):
            # 预设已管理的Bot
            monitor.managed_bots.add("bot1")
            monitor.managed_bots.add("bot2")
            monitor.managed_bots.add("bot5")  # 添加一个将在Opera中变为非活跃的Bot

            # 模拟进程
            mock_process = mock.MagicMock()
            mock_process.is_alive.return_value = True
            monitor.processes["bot5"] = mock_process

            # 模拟BotTool.run返回值
            monitor.bot_tool.run.return_value = "mock_result"

            # 模拟parser.parse_response返回值 - 包含新的符合条件的Bot和已管理但变为非活跃的Bot
            monitor.parser.parse_response.return_value = (
                200,
                [
                    {"id": "bot1", "name": "前端-测试Bot1", "isActive": True},  # 已管理且活跃
                    {"id": "bot2", "name": "前端-测试Bot2", "isActive": True},  # 已管理且活跃
                    {"id": "bot3", "name": "前端-新Bot", "isActive": False},  # 新的符合条件Bot
                    {"id": "bot4", "name": "其他Bot", "isActive": False},  # 不符合条件
                    {"id": "bot5", "name": "前端-已变非活跃", "isActive": False},  # 已管理但变为非活跃
                ],
            )

            # 模拟_start_bot_manager方法
            with mock.patch.object(monitor, "_start_bot_manager") as mock_start:
                await monitor._check_bots()

                # 验证调用了_start_bot_manager两次:
                # 1. 为新的符合条件的Bot启动进程
                # 2. 为已管理但变为非活跃的Bot重新启动进程
                assert mock_start.call_count == 3

                # 验证为新的符合条件的Bot启动了进程
                mock_start.assert_any_call("bot3", "前端-新Bot")

                # 验证为已管理但变为非活跃的Bot重新启动了进程
                mock_start.assert_any_call("bot5", "前端-已变非活跃")

                # 验证已经从管理列表中移除了变为非活跃的Bot（在重新启动前）
                assert "bot5" not in monitor.managed_bots

                # 验证终止了已存在的进程
                mock_process.terminate.assert_called_once()
                mock_process.join.assert_called_once()
                assert "bot5" not in monitor.processes

    @pytest.mark.asyncio
    async def test_check_bots_no_inactive_managed_bots(self, monitor):
        """测试当没有已管理但变为非活跃的Bot时的情况"""
        # 增加BOT_NAME_FILTER常量的模拟，确保与代码匹配
        with mock.patch("src.core.entrypoints.crew_manager_main.BOT_NAME_FILTER", "前端-"):
            # 预设已管理的Bot
            monitor.managed_bots.add("bot1")
            monitor.managed_bots.add("bot2")

            # 模拟BotTool.run返回值
            monitor.bot_tool.run.return_value = "mock_result"

            # 模拟parser.parse_response返回值 - 所有已管理的Bot都是活跃的
            monitor.parser.parse_response.return_value = (
                200,
                [
                    {"id": "bot1", "name": "前端-测试Bot1", "isActive": True},  # 已管理且活跃
                    {"id": "bot2", "name": "前端-测试Bot2", "isActive": True},  # 已管理且活跃
                    {"id": "bot3", "name": "前端-新Bot", "isActive": False},  # 新的符合条件Bot
                    {"id": "bot4", "name": "其他Bot", "isActive": False},  # 不符合条件
                ],
            )

            # 模拟_start_bot_manager方法
            with mock.patch.object(monitor, "_start_bot_manager") as mock_start:
                await monitor._check_bots()

                # 验证只为新的符合条件的Bot启动了进程
                mock_start.assert_called_once_with("bot3", "前端-新Bot")

                # 验证已管理的Bot仍在管理列表中
                assert "bot1" in monitor.managed_bots
                assert "bot2" in monitor.managed_bots

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
