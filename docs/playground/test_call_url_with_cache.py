"""当设置了 mock_get.side_effect = logging_effect 时：
    mock_get 不再有自己的行为
    所有对 mock_get 的调用都会被直接转发给 logging_effect
    side_effect 成为了唯一的执行路径
"""

import unittest
from unittest.mock import patch
import requests
import logging
from datetime import datetime, timedelta
import json
import os
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class URLCache:
    def __init__(self, ttl_seconds=3600, cache_dir=None):  # 默认缓存1小时
        self.ttl_seconds = ttl_seconds
        # 设置缓存目录，默认在当前文件目录下的 .cache
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        self.cache_dir = cache_dir or os.path.join(current_file_dir, '.cache')
        # 确保缓存目录存在
        os.makedirs(self.cache_dir, exist_ok=True)
        logger.info(f"使用缓存目录: {self.cache_dir}")

    def _get_cache_path(self, url):
        """获取URL对应的缓存文件路径"""
        # 将URL转换为合法的文件名
        import hashlib
        filename = hashlib.md5(url.encode()).hexdigest() + '.json'
        return os.path.join(self.cache_dir, filename)

    def get(self, url):
        """获取缓存的响应"""
        cache_path = self._get_cache_path(url)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    # 检查是否过期
                    if datetime.fromisoformat(cached_data['expires']) > datetime.now():
                        logger.info(f"🎯 命中缓存: {url}")
                        return cached_data['data']
                    else:
                        logger.info(f"⌛ 缓存过期: {url}")
                        os.remove(cache_path)
            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning(f"读取缓存失败: {e}")
                if os.path.exists(cache_path):
                    os.remove(cache_path)
        return None

    def set(self, url, data):
        """设置缓存"""
        cache_path = self._get_cache_path(url)
        cache_data = {
            'data': data,
            'expires': (datetime.now() + timedelta(seconds=self.ttl_seconds)).isoformat()
        }
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            logger.info(f"💾 已缓存: {url} -> {cache_path}")
        except OSError as e:
            logger.error(f"写入缓存失败: {e}")

    def clear(self):
        """清除所有缓存"""
        for file in os.listdir(self.cache_dir):
            if file.endswith('.json'):
                os.remove(os.path.join(self.cache_dir, file))
        logger.info("🧹 已清除所有缓存")


# 创建全局缓存实例
url_cache = URLCache()


def fetch_data(url, use_cache=True):
    """获取URL响应的详细信息，支持缓存

    Args:
        url (str): 请求的URL
        use_cache (bool): 是否使用缓存，默认True

    Returns:
        dict: 包含状态码、响应内容等信息的字典
    """
    if use_cache:
        cached_data = url_cache.get(url)
        if cached_data:
            return cached_data

    response = requests.get(url)
    result = {
        'status_code': response.status_code,
        'content': response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text,
        'headers': dict(response.headers)
    }

    if use_cache and response.status_code == 200:  # 只缓存成功的响应
        url_cache.set(url, result)

    return result


class EnhancedUrlTest(unittest.TestCase):
    def setUp(self):
        """测试开始前清理缓存"""
        url_cache.clear()

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
            # 测试缓存功能
            logger.info("测试缓存功能 - 第一次请求")
            result1 = fetch_data('https://httpbin.org/json')
            self.assertEqual(result1['status_code'], 200)

            # 验证缓存文件已创建
            cache_file = url_cache._get_cache_path('https://httpbin.org/json')
            self.assertTrue(os.path.exists(cache_file))

            logger.info("测试缓存功能 - 第二次请求（应该使用缓存）")
            result2 = fetch_data('https://httpbin.org/json')
            self.assertEqual(result2['status_code'], 200)
            self.assertEqual(result1['content'], result2['content'])

            # 测试不使用缓存
            logger.info("测试不使用缓存")
            result3 = fetch_data('https://httpbin.org/json', use_cache=False)
            self.assertEqual(result3['status_code'], 200)

            # 测试错误响应（不应该被缓存）
            result4 = fetch_data('https://httpbin.org/status/404')
            self.assertEqual(result4['status_code'], 404)

            # 验证错误响应没有被缓存
            error_cache_file = url_cache._get_cache_path('https://httpbin.org/status/404')
            self.assertFalse(os.path.exists(error_cache_file))

            # 再次请求404（验证没有被缓存）
            result5 = fetch_data('https://httpbin.org/status/404')
            self.assertEqual(result5['status_code'], 404)

        except requests.exceptions.ConnectionError:
            self.skipTest("需要网络连接")


if __name__ == '__main__':
    unittest.main(verbosity=2)
