import unittest
from unittest.mock import patch, Mock, call
import requests
import logging
from url_service import UrlService, ApiClient

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestComplexUrlService(unittest.TestCase):
    def setUp(self):
        """测试前的设置"""
        self.base_url = 'https://httpbin.org'
        self.service = UrlService(self.base_url)
        self.client = ApiClient(self.service)

    def test_complex_url_chain(self):
        """测试复杂的URL调用链，包含多层调用和缓存"""
        # 配置mock会话
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}

        with patch.object(self.service.session, 'get', return_value=mock_response) as mock_get:
            # 执行测试
            endpoint = 'api/test'
            result = self.client.fetch_endpoint_status(endpoint)

            # 验证结果
            self.assertEqual(result, 200)

            # 验证调用链
            expected_url = f"{self.base_url}/{endpoint}"
            mock_get.assert_called_with(expected_url)

            # 测试缓存效果
            result2 = self.client.fetch_endpoint_status(endpoint)  # 第二次调用
            self.assertEqual(result2, 200)
            # 由于缓存，实际的HTTP请求应该只发生一次
            mock_get.assert_called_once()

    def test_retry_mechanism(self):
        """测试重试机制"""
        # 配置mock响应
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {"data": "test"}

        with patch.object(self.service.session, 'get') as mock_get:
            # 设置前两次失败，第三次成功
            mock_get.side_effect = [
                requests.exceptions.ConnectionError("Network error"),
                requests.exceptions.ConnectionError("Network error"),
                success_response
            ]

            # 执行测试
            result = self.client.fetch_endpoint_status('api/test')

            # 验证结果
            self.assertEqual(result, 200)
            # 验证重试次数
            self.assertEqual(mock_get.call_count, 3)

    def test_error_handling(self):
        """测试错误处理"""
        with patch.object(self.service.session, 'get') as mock_get:
            mock_get.side_effect = requests.exceptions.RequestException("Fatal error")

            with self.assertRaises(requests.exceptions.RequestException):
                self.client.fetch_endpoint_status('api/error')


if __name__ == '__main__':
    unittest.main(verbosity=2)
