"""pytest配置文件，提供通用的测试工具和fixture"""
import os
import pytest
from contextlib import contextmanager
from typing import Optional, Generator

from src.crewai_ext.config.llm_factory import get_llm


@pytest.fixture
def cached_llm():
    """提供一个使用缓存的LLM实例"""
    return get_llm(use_cache=True)


@contextmanager
def use_cached_llm(cache_dir: Optional[str] = None) -> Generator:
    """临时启用LLM缓存的上下文管理器
    
    Args:
        cache_dir: 可选的缓存目录路径
        
    Example:
        ```python
        from src.crewai_ext.tests.conftest import use_cached_llm
        
        def test_something():
            with use_cached_llm():
                llm = get_llm()  # 这个LLM实例会使用缓存
                # 进行测试...
        ```
    """
    old_cache = os.environ.get("USE_CACHED_LLM")
    os.environ["USE_CACHED_LLM"] = "true"
    if cache_dir:
        os.environ["CREWAI_CACHE_DIR"] = cache_dir

    try:
        yield
    finally:
        if old_cache is None:
            del os.environ["USE_CACHED_LLM"]
        else:
            os.environ["USE_CACHED_LLM"] = old_cache

        if cache_dir:
            del os.environ["CREWAI_CACHE_DIR"]
