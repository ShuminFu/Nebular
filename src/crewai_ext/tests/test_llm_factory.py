"""LLM工厂模块的测试用例"""
import os
import pytest
from src.crewai_ext.config.llm_factory import get_llm
from src.crewai_ext.tools.cached_llm import CachedLLM
from src.crewai_ext.tests.conftest import use_cached_llm


def test_get_llm_with_cache_fixture(cached_llm):
    """使用pytest fixture方式获取缓存LLM"""
    assert isinstance(cached_llm, CachedLLM)


def test_get_llm_with_context_manager():
    """使用上下文管理器方式临时启用缓存"""
    # 默认不使用缓存
    llm = get_llm()
    assert not isinstance(llm, CachedLLM)

    # 在上下文中使用缓存
    with use_cached_llm():
        llm = get_llm()
        assert isinstance(llm, CachedLLM)

    # 上下文结束后恢复默认行为
    llm = get_llm()
    assert not isinstance(llm, CachedLLM)


def test_get_llm_with_env_var():
    """使用环境变量方式启用缓存"""
    # 设置环境变量
    os.environ["USE_CACHED_LLM"] = "true"
    llm = get_llm()
    assert isinstance(llm, CachedLLM)

    # 清理环境变量
    del os.environ["USE_CACHED_LLM"]
    llm = get_llm()
    assert not isinstance(llm, CachedLLM)


def test_get_llm_with_custom_cache_dir():
    """测试自定义缓存目录"""
    test_cache_dir = ".test_cache"
    with use_cached_llm(cache_dir=test_cache_dir):
        llm = get_llm()
        assert isinstance(llm, CachedLLM)
        # 这里可以添加检查缓存目录是否正确的断言
