import unittest
from unittest.mock import patch
import requests
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_data(url):
    """获取URL状态码"""
    return requests.get(url).status_code

class EnhancedUrlTest(unittest.TestCase):
    # 修正后的测试用例
    @patch('requests.get', wraps=requests.get)  # 显式使用wraps
    def test_logging_with_wrapped(self, mock_get):
        """带日志记录的完整测试案例"""
        # 定义日志记录函数
        def logging_effect(url, *args, **kwargs):
            """带日志的副作用函数"""
            logger.info(f"🌐 请求URL: {url}")
            
            # 调用原始请求（通过wrapped属性）
            original_func = mock_get._mock_wraps  # 正确的访问方式
            
            # 使用闭包捕获原始函数引用
            # original_get = requests.get  # 在mock生效前捕获
    
            response = original_func(url, *args, **kwargs)
            
            logger.info(f"🔄 收到响应: {response.status_code}")
            return response

        # 应用副作用函数
        mock_get.side_effect = logging_effect

        try:
            # 执行测试
            result = fetch_data('https://httpbin.org/get')
            self.assertEqual(result, 200)
            
            # 验证调用
            mock_get.assert_called_once_with('https://httpbin.org/get')
            print(f"调用参数: {mock_get.call_args[0][0]}")
            
        except requests.exceptions.ConnectionError:
            self.skipTest("需要网络连接")

if __name__ == '__main__':
    unittest.main(verbosity=2)
