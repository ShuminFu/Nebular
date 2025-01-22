import unittest
from unittest.mock import patch
import requests
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_data(url):
    """获取URL响应的详细信息
    
    Returns:
        dict: 包含状态码、响应内容等信息的字典
    """
    response = requests.get(url)
    return {
        'status_code': response.status_code,
        'content': response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text,
        'headers': dict(response.headers)
    }

class EnhancedUrlTest(unittest.TestCase):
    @patch('requests.get', wraps=requests.get)
    def test_different_responses(self, mock_get):
        """测试不同的响应类型和状态码"""
        def logging_effect(url, *args, **kwargs):
            logger.info(f"🌐 请求URL: {url}")
            
            # 调用原始请求（通过wrapped属性）
            original_func = mock_get._mock_wraps  # 正确的访问方式
            
            # 使用闭包捕获原始函数引用
            # original_get = requests.get  # 在mock生效前捕获
    
            response = original_func(url, *args, **kwargs)
            logger.info(f"🔄 收到响应: {response.status_code}")
            return response

        mock_get.side_effect = logging_effect

        try:
            # 测试 200 OK with JSON
            result = fetch_data('https://httpbin.org/json')
            self.assertEqual(result['status_code'], 200)
            self.assertIn('slideshow', result['content'])

            # 测试 404 Not Found
            result = fetch_data('https://httpbin.org/status/404')
            self.assertEqual(result['status_code'], 404)

            # 测试 500 Internal Server Error
            result = fetch_data('https://httpbin.org/status/500')
            self.assertEqual(result['status_code'], 500)

            # 测试带延迟的响应
            result = fetch_data('https://httpbin.org/delay/1')
            self.assertEqual(result['status_code'], 200)
            self.assertIn('url', result['content'])

        except requests.exceptions.ConnectionError:
            self.skipTest("需要网络连接")

if __name__ == '__main__':
    unittest.main(verbosity=2)
