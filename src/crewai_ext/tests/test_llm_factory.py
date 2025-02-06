"""LLM工厂模块的测试用例"""
import os
import shutil
from src.crewai_ext.config.llm_factory import get_llm
import litellm
from litellm.caching import Cache


def setup_module():
    """测试模块开始前的设置"""
    cleanup_cache()


def teardown_module():
    """测试模块结束后的清理"""
    cleanup_cache()
    litellm.disable_cache()


def cleanup_cache():
    """清理缓存目录"""
    cache_dir = '.test_cache'
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)
    os.makedirs(cache_dir, exist_ok=True)


def test_get_llm_without_cache():
    """测试获取无缓存的LLM"""
    litellm.disable_cache()
    llm = get_llm()
    assert not hasattr(litellm, 'cache') or litellm.cache is None


def test_get_llm_with_cache():
    """测试获取带缓存的LLM"""
    cache_dir = '.test_cache'
    llm = get_llm(
        use_cache=True,
        cache_dir=cache_dir
    )
    assert hasattr(litellm, 'cache')
    assert isinstance(litellm.cache, Cache)
    assert litellm.cache.type == "disk"
    assert os.path.exists(cache_dir)


def test_get_llm_with_custom_cache_dir():
    """测试自定义缓存目录"""
    custom_cache_dir = '.custom_test_cache'
    if os.path.exists(custom_cache_dir):
        shutil.rmtree(custom_cache_dir)

    llm = get_llm(
        use_cache=True,
        cache_dir=custom_cache_dir
    )

    assert hasattr(litellm, 'cache')
    assert isinstance(litellm.cache, Cache)
    assert os.path.exists(custom_cache_dir)

    # 清理
    shutil.rmtree(custom_cache_dir)

def test_get_llm_with_env_var():
    """使用环境变量方式启用缓存"""
    # 设置环境变量
    os.environ["USE_CACHED_LLM"] = "true"
    llm = get_llm()
    assert hasattr(litellm, 'cache')
    assert isinstance(litellm.cache, Cache)

    # 清理环境变量
    del os.environ["USE_CACHED_LLM"]
    litellm.disable_cache()
    llm = get_llm()
    assert not hasattr(litellm, 'cache') or litellm.cache is None
