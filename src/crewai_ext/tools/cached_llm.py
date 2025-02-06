"""测试在CrewAI场景中使用LLM缓存的示例。
结合CrewAI的Agent和Task使用LLM缓存，避免重复调用API。
"""
import os

from typing import List, Dict, Optional, Any
from crewai import LLM
from src.tools.llm_cache import LLMCache


# 创建专门用于CrewAI的LLM缓存实例
crewai_llm_cache = LLMCache(cache_dir='.crewai_llm_cache')


class CachedLLM(LLM):
    """支持缓存的LLM模型"""

    def __init__(self, cache=None, **kwargs):
        """初始化缓存LLM

        Args:
            cache: LLMCache实例，用于缓存LLM调用结果
            **kwargs: 传递给父类LLM的参数
        """
        super().__init__(**kwargs)
        self.cache = cache or crewai_llm_cache

    def call(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[dict]] = None,
        callbacks: Optional[List[Any]] = None,
        available_functions: Optional[Dict[str, Any]] = None,
    ) -> str:
        """重写call方法，添加缓存支持

        Args:
            messages: 对话消息列表
            tools: 可选的函数模式列表
            callbacks: 可选的回调函数列表
            available_functions: 可用函数字典

        Returns:
            str: LLM响应文本或工具调用结果
        """
        # 创建缓存键需要考虑的所有参数
        cache_params = {
            'model': self.model,
            'messages': messages,
            'temperature': self.temperature,
            'top_p': self.top_p,
            'n': self.n,
            'stop': self.stop,
            'max_tokens': self.max_tokens or self.max_completion_tokens,
            'presence_penalty': self.presence_penalty,
            'frequency_penalty': self.frequency_penalty,
            'logit_bias': self.logit_bias,
            'response_format': self.response_format,
            'seed': self.seed,
            'tools': tools,
            'api_version': self.api_version,
        }

        # 尝试从缓存获取响应
        cached_response = self.cache.get(**cache_params)

        if cached_response:
            # 处理缓存命中的回调
            if callbacks and len(callbacks) > 0:
                for callback in callbacks:
                    if hasattr(callback, "log_success_event"):
                        callback.log_success_event(
                            kwargs=cache_params,
                            response_obj={"usage": {"cached": True}},
                            start_time=0,
                            end_time=0,
                        )
            return cached_response

        # 如果没有缓存，调用原始方法
        response = super().call(
            messages=messages,
            tools=tools,
            callbacks=callbacks,
            available_functions=available_functions
        )

        # 缓存响应
        self.cache.set(
            response_data=response,
            **cache_params
        )

        return response

    def supports_function_calling(self) -> bool:
        """检查模型是否支持函数调用"""
        return super().supports_function_calling()

    def supports_stop_words(self) -> bool:
        """检查模型是否支持停止词"""
        return super().supports_stop_words()

    def get_context_window_size(self) -> int:
        """获取上下文窗口大小"""
        return super().get_context_window_size()


def get_test_llm():
    """根据环境变量返回测试用的LLM实例"""
    if os.getenv("USE_CACHED_LLM", "true").lower() == "true":
        return CachedLLM(
            model="mock-model",
            cache=LLMCache(cache_dir='.test_cache'),
            api_key="mock_key"
        )
    return LLM(model="mock-model", api_key="mock_key")
