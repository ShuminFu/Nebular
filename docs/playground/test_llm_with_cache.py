"""用于测试LLM生成的缓存机制。
基于URL缓存改造，支持对LLM请求响应的缓存，避免重复调用API。
"""

import unittest
from unittest.mock import patch
import logging
import json
import os
from datetime import datetime, timedelta
import hashlib

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LLMCache:
    """专门用于缓存LLM响应的缓存类"""

    def __init__(self, ttl_seconds=3600, cache_dir=None):
        self.ttl_seconds = ttl_seconds
        # 设置缓存目录，默认在当前文件目录下的 .llm_cache
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        self.cache_dir = cache_dir or os.path.join(current_file_dir, '.llm_cache')
        # 确保缓存目录存在
        os.makedirs(self.cache_dir, exist_ok=True)
        logger.info(f"使用LLM缓存目录: {self.cache_dir}")

    def _generate_cache_key(self, model: str, messages: list, **kwargs) -> str:
        """生成缓存键
        
        考虑所有可能影响LLM输出的参数，包括：
        - 模型名称
        - 消息内容
        - 其他参数(temperature, top_p等)
        """
        # 创建一个包含所有参数的字典
        cache_dict = {
            'model': model,
            'messages': messages,
            **kwargs
        }
        # 将字典转换为规范化的JSON字符串
        cache_str = json.dumps(cache_dict, sort_keys=True)
        # 使用MD5生成缓存键
        return hashlib.md5(cache_str.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f"{cache_key}.json")

    def get(self, model: str, messages: list, **kwargs) -> dict:
        """获取缓存的LLM响应
        
        Args:
            model: 模型名称
            messages: 消息列表
            **kwargs: 其他参数(temperature, top_p等)
            
        Returns:
            dict: 缓存的响应数据，如果没有缓存则返回None
        """
        cache_key = self._generate_cache_key(model, messages, **kwargs)
        cache_path = self._get_cache_path(cache_key)

        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    # 检查是否过期
                    if datetime.fromisoformat(cached_data['expires']) > datetime.now():
                        logger.info(f"🎯 命中LLM缓存: {model}")
                        return cached_data['data']
                    else:
                        logger.info(f"⌛ LLM缓存过期: {model}")
                        os.remove(cache_path)
            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning(f"读取LLM缓存失败: {e}")
                if os.path.exists(cache_path):
                    os.remove(cache_path)
        return None

    def set(self, model: str, messages: list, response_data: dict, **kwargs):
        """设置LLM响应缓存
        
        Args:
            model: 模型名称
            messages: 消息列表
            response_data: 响应数据
            **kwargs: 其他参数(temperature, top_p等)
        """
        cache_key = self._generate_cache_key(model, messages, **kwargs)
        cache_path = self._get_cache_path(cache_key)

        cache_data = {
            'data': response_data,
            'expires': (datetime.now() + timedelta(seconds=self.ttl_seconds)).isoformat()
        }

        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            logger.info(f"💾 已缓存LLM响应: {model} -> {cache_path}")
        except OSError as e:
            logger.error(f"写入LLM缓存失败: {e}")

    def clear(self):
        """清除所有LLM缓存"""
        for file in os.listdir(self.cache_dir):
            if file.endswith('.json'):
                os.remove(os.path.join(self.cache_dir, file))
        logger.info("🧹 已清除所有LLM缓存")


# 创建全局LLM缓存实例
llm_cache = LLMCache()


def call_llm_with_cache(model: str, messages: list, use_cache=True, **kwargs) -> dict:
    """调用LLM接口，支持缓存
    
    Args:
        model: 模型名称
        messages: 消息列表
        use_cache: 是否使用缓存，默认True
        **kwargs: 其他参数(temperature, top_p等)
        
    Returns:
        dict: LLM响应数据
    """
    if use_cache:
        cached_response = llm_cache.get(model, messages, **kwargs)
        if cached_response:
            return cached_response

    # 这里替换为实际的LLM调用
    # 示例：response = openai.ChatCompletion.create(model=model, messages=messages, **kwargs)
    response = {
        'model': model,
        'choices': [
            {
                'message': {
                    'role': 'assistant',
                    'content': 'This is a mock response'
                }
            }
        ]
    }

    if use_cache:
        llm_cache.set(model, messages, response, **kwargs)

    return response


class TestLLMWithCache(unittest.TestCase):
    """测试带缓存的LLM调用"""

    def setUp(self):
        """测试开始前清理缓存"""
        llm_cache.clear()

    def test_llm_cache(self):
        """测试LLM缓存功能"""
        model = "gpt-3.5-turbo"
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"}
        ]

        # 第一次调用（应该实际调用API）
        logger.info("测试LLM缓存 - 第一次调用")
        result1 = call_llm_with_cache(model, messages, temperature=0.7)
        self.assertIn('choices', result1)

        # 验证缓存文件已创建
        cache_key = llm_cache._generate_cache_key(model, messages, temperature=0.7)
        cache_file = llm_cache._get_cache_path(cache_key)
        self.assertTrue(os.path.exists(cache_file))

        # 第二次调用（应该使用缓存）
        logger.info("测试LLM缓存 - 第二次调用（应该使用缓存）")
        result2 = call_llm_with_cache(model, messages, temperature=0.7)
        self.assertEqual(result1, result2)

        # 测试不同参数生成不同的缓存键
        logger.info("测试不同参数的缓存键")
        result3 = call_llm_with_cache(model, messages, temperature=0.8)
        cache_key2 = llm_cache._generate_cache_key(model, messages, temperature=0.8)
        self.assertNotEqual(cache_key, cache_key2)

        # 测试禁用缓存
        logger.info("测试禁用缓存")
        result4 = call_llm_with_cache(model, messages, use_cache=False)
        self.assertIn('choices', result4)


if __name__ == '__main__':
    unittest.main(verbosity=2)
