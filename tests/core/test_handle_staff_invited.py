import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import UUID
import json

from src.core.crew_process import BaseCrewProcess, CrewManager, CrewRunner


class TestHandleStaffInvited(unittest.IsolatedAsyncioTestCase):
    """测试处理Staff邀请的方法"""

    async def asyncSetUp(self):
        """设置异步测试环境"""
        # 由于BaseCrewProcess是抽象类，我们使用其子类进行测试
        with patch("src.core.crew_process.OperaSignalRClient"):
            with patch("src.core.crew_process.get_logger_with_trace_id"):
                with patch("src.core.crew_process.RunnerChatCrew"):
                    with patch("src.core.crew_process.RunnerCodeGenerationCrew"):
                        # 创建CrewManager实例用于测试
                        self.crew_manager = CrewManager()
                        # 创建CrewRunner实例用于测试
                        self.crew_runner = CrewRunner(bot_id=UUID("12345678-1234-5678-1234-567812345678"))

        # 模拟日志
        self.crew_manager.log = MagicMock()
        self.crew_runner.log = MagicMock()

    async def test_handle_staff_invited_manager(self):
        """测试CrewManager处理Staff邀请"""
        # 设置模拟对象 - 使用内部导入的模拟方式
        mock_tool_instance = MagicMock()
        mock_tool_instance.run.return_value = "状态码: 200, 详细内容: 接受邀请成功"
        mock_tool = MagicMock(return_value=mock_tool_instance)
        mock_acceptance = MagicMock()

        # 创建邀请数据
        invite_data = {
            "opera_id": UUID("99a51bfa-0b95-46e5-96b3-e3cfc021a6b2"),
            "invitation_id": UUID("abcdef12-3456-7890-abcd-ef1234567890"),
            "parameter": {"key": "value"},
            "tags": "test,tags",
            "roles": "CrewManager",
            "permissions": "manager",
        }

        # 使用patch应用于不同的导入
        with patch("src.crewai_ext.tools.opera_api.staff_invitation_api_tool.StaffInvitationTool", mock_tool):
            with patch("src.opera_service.api.models.StaffInvitationForAcceptance", mock_acceptance):
                # 调用被测试方法
                await self.crew_manager._handle_staff_invited(invite_data)

        # 验证创建了StaffInvitationForAcceptance对象
        mock_acceptance.assert_called_once()

        # 验证调用了StaffInvitationTool的run方法
        mock_tool_instance.run.assert_called_once()

        # 验证日志记录
        self.crew_manager.log.info.assert_called_with(f"自动接受邀请结果: 状态码: 200, 详细内容: 接受邀请成功")

    async def test_handle_staff_invited_runner(self):
        """测试CrewRunner处理Staff邀请"""
        # 设置模拟对象 - 使用内部导入的模拟方式
        mock_tool_instance = MagicMock()
        mock_tool_instance.run.return_value = "状态码: 200, 详细内容: 接受邀请成功"
        mock_tool = MagicMock(return_value=mock_tool_instance)
        mock_acceptance = MagicMock()

        # 创建邀请数据
        invite_data = {
            "opera_id": UUID("99a51bfa-0b95-46e5-96b3-e3cfc021a6b2"),
            "invitation_id": UUID("abcdef12-3456-7890-abcd-ef1234567890"),
            "parameter": {"key": "value"},
            "tags": "test,tags",
            "roles": "CodeGenerator",
            "permissions": "basic",
        }

        # 使用patch应用于不同的导入
        with patch("src.crewai_ext.tools.opera_api.staff_invitation_api_tool.StaffInvitationTool", mock_tool):
            with patch("src.opera_service.api.models.StaffInvitationForAcceptance", mock_acceptance):
                # 调用被测试方法
                await self.crew_runner._handle_staff_invited(invite_data)

        # 验证创建了StaffInvitationForAcceptance对象
        mock_acceptance.assert_called_once()

        # 验证调用了StaffInvitationTool的run方法
        mock_tool_instance.run.assert_called_once()

        # 验证日志记录
        self.crew_runner.log.info.assert_called_with(f"自动接受邀请结果: 状态码: 200, 详细内容: 接受邀请成功")

    async def test_handle_staff_invited_missing_fields(self):
        """测试处理缺少必要字段的Staff邀请"""
        # 创建缺少字段的邀请数据
        invite_data = {
            "opera_id": UUID("99a51bfa-0b95-46e5-96b3-e3cfc021a6b2"),
            # 缺少invitation_id
            "parameter": {"key": "value"},
            "tags": "test,tags",
            # 缺少roles
            "permissions": "manager",
        }

        # 调用被测试方法
        await self.crew_manager._handle_staff_invited(invite_data)

        # 验证日志记录错误
        self.crew_manager.log.error.assert_called_once()
        error_msg = self.crew_manager.log.error.call_args[0][0]
        self.assertTrue("缺少必要的字段" in error_msg)

    async def test_handle_staff_invited_exception(self):
        """测试处理接受邀请时发生异常的情况"""
        # 设置模拟对象 - 使用内部导入的模拟方式
        mock_tool_instance = MagicMock()
        mock_tool_instance.run.side_effect = Exception("测试异常")
        mock_tool = MagicMock(return_value=mock_tool_instance)
        mock_acceptance = MagicMock()

        # 创建邀请数据
        invite_data = {
            "opera_id": UUID("99a51bfa-0b95-46e5-96b3-e3cfc021a6b2"),
            "invitation_id": UUID("abcdef12-3456-7890-abcd-ef1234567890"),
            "parameter": {"key": "value"},
            "tags": "test,tags",
            "roles": "CrewManager",
            "permissions": "manager",
        }

        # 使用patch应用于不同的导入
        with patch("src.crewai_ext.tools.opera_api.staff_invitation_api_tool.StaffInvitationTool", mock_tool):
            with patch("src.opera_service.api.models.StaffInvitationForAcceptance", mock_acceptance):
                # 调用被测试方法
                await self.crew_manager._handle_staff_invited(invite_data)

        # 验证创建了StaffInvitationForAcceptance对象
        mock_acceptance.assert_called_once()

        # 验证调用了StaffInvitationTool的run方法
        mock_tool_instance.run.assert_called_once()

        # 验证日志记录错误
        self.crew_manager.log.error.assert_called_with("自动接受邀请失败: 测试异常")
        self.crew_manager.log.exception.assert_called_with("详细错误信息:")


if __name__ == "__main__":
    unittest.main()
