import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import json
from uuid import UUID
import sys
import os

# 添加项目根目录到Python路径
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.opera_service.signalr_client.opera_signalr_client import OperaSignalRClient


class TestOperaSignalRClient(unittest.IsolatedAsyncioTestCase):
    """测试OperaSignalRClient类"""

    async def asyncSetUp(self):
        """设置异步测试环境"""
        # 使用patch创建OperaSignalRClient实例，避免实际连接
        with patch("src.opera_service.signalr_client.opera_signalr_client.SignalRClient"):
            self.client = OperaSignalRClient(url="http://test.url", bot_id="12345678-1234-5678-1234-567812345678")

        # 模拟日志和回调
        self.client.log = MagicMock()
        self.client.callbacks["on_staff_invited"] = AsyncMock()
        self._execute_callback_mock = AsyncMock()
        self.client._execute_callback = self._execute_callback_mock

    async def test_handle_staff_invited(self):
        """测试_handle_staff_invited方法正常调用回调"""
        # 构造邀请参数
        args = {
            "operaId": "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2",
            "invitationId": "abcdef12-3456-7890-abcd-ef1234567890",
            "parameter": '{"key": "value"}',
            "tags": "test,tags",
            "roles": "CrewManager",
            "permissions": "manager",
        }

        # 调用被测试方法
        await self.client._handle_staff_invited(args)

        # 验证执行了回调
        self._execute_callback_mock.assert_called_once()

        # 检查回调参数
        callback_name, callback, data = self._execute_callback_mock.call_args[0]
        self.assertEqual(callback_name, "on_staff_invited")
        self.assertEqual(callback, self.client.callbacks["on_staff_invited"])

        # 验证构造的invite_data正确
        self.assertEqual(data["opera_id"], UUID(args["operaId"]))
        self.assertEqual(data["invitation_id"], UUID(args["invitationId"]))
        self.assertEqual(data["parameter"], {"key": "value"})
        self.assertEqual(data["tags"], args["tags"])
        self.assertEqual(data["roles"], args["roles"])
        self.assertEqual(data["permissions"], args["permissions"])

    async def test_handle_staff_invited_without_callback(self):
        """测试没有设置回调时的_handle_staff_invited方法"""
        # 移除回调
        self.client.callbacks["on_staff_invited"] = None

        # 构造邀请参数
        args = {
            "operaId": "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2",
            "invitationId": "abcdef12-3456-7890-abcd-ef1234567890",
            "parameter": '{"key": "value"}',
            "tags": "test,tags",
            "roles": "CrewManager",
            "permissions": "manager",
        }

        # 调用被测试方法
        await self.client._handle_staff_invited(args)

        # 验证未执行回调
        self._execute_callback_mock.assert_not_called()

        # 验证记录了警告日志
        self.client.log.warning.assert_called_with("收到Staff邀请事件，但未设置处理回调")

    async def test_handle_staff_invited_missing_fields(self):
        """测试缺少必要字段时的_handle_staff_invited方法"""
        # 构造缺少必要字段的邀请参数
        args = {
            "operaId": "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2",
            # 缺少invitationId
            "parameter": '{"key": "value"}',
            "tags": "test,tags",
            # 缺少roles
            "permissions": "manager",
        }

        # 调用被测试方法
        await self.client._handle_staff_invited(args)

        # 验证未执行回调
        self._execute_callback_mock.assert_not_called()

        # 验证记录了错误日志
        self.client.log.error.assert_called_once()
        error_msg = self.client.log.error.call_args[0][0]
        self.assertTrue("缺少必要的字段" in error_msg)

    async def test_handle_staff_invited_json_decode_error(self):
        """测试JSON解析错误时的_handle_staff_invited方法"""
        # 构造包含无效JSON的邀请参数
        args = {
            "operaId": "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2",
            "invitationId": "abcdef12-3456-7890-abcd-ef1234567890",
            "parameter": "{invalid json}",  # 无效的JSON
            "tags": "test,tags",
            "roles": "CrewManager",
            "permissions": "manager",
        }

        # 调用被测试方法
        await self.client._handle_staff_invited(args)

        # 验证未执行回调
        self._execute_callback_mock.assert_not_called()

        # 验证记录了错误日志
        self.client.log.error.assert_called_once()
        error_msg = self.client.log.error.call_args[0][0]
        self.assertTrue("解析参数JSON失败" in error_msg)

    async def test_handle_staff_invited_exception(self):
        """测试处理过程中发生异常时的_handle_staff_invited方法"""
        # 设置_execute_callback抛出异常
        self._execute_callback_mock.side_effect = Exception("测试异常")

        # 构造邀请参数
        args = {
            "operaId": "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2",
            "invitationId": "abcdef12-3456-7890-abcd-ef1234567890",
            "parameter": '{"key": "value"}',
            "tags": "test,tags",
            "roles": "CrewManager",
            "permissions": "manager",
        }

        # 调用被测试方法
        await self.client._handle_staff_invited(args)

        # 验证尝试执行回调
        self._execute_callback_mock.assert_called_once()

        # 验证记录了错误日志
        self.client.log.error.assert_called_with("处理Staff邀请事件失败: 测试异常")
        self.client.log.exception.assert_called_with("详细错误信息:")


if __name__ == "__main__":
    unittest.main()
