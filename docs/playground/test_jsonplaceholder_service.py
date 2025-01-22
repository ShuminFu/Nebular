import unittest
import requests
import logging
from url_service import UrlService, ApiClient

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestJsonPlaceholderService(unittest.TestCase):
    def setUp(self):
        """测试前的设置"""
        self.base_url = 'https://jsonplaceholder.typicode.com'
        self.service = UrlService(self.base_url)
        self.client = ApiClient(self.service)

    def test_real_api_call(self):
        """测试实际API调用"""
        # 直接调用真实API
        endpoint = 'posts/1'
        result = self.client.fetch_endpoint_status(endpoint)
        self.assertEqual(result, 200)

        # 测试缓存是否工作
        result2 = self.client.fetch_endpoint_status(endpoint)
        self.assertEqual(result2, 200)

    def test_multiple_endpoints(self):
        """测试多个不同的端点"""
        endpoints = ['posts/1', 'comments/1', 'users/1']
        for endpoint in endpoints:
            result = self.client.fetch_endpoint_status(endpoint)
            self.assertEqual(result, 200)

    def test_nonexistent_resource(self):
        """测试访问不存在的资源"""
        with self.assertRaises(requests.exceptions.HTTPError):
            self.client.fetch_endpoint_status('posts/999999')


if __name__ == '__main__':
    unittest.main(verbosity=2)
