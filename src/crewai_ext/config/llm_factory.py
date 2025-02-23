"""LLM工厂模块，提供动态LLM配置和实例化功能。

此模块负责根据环境变量和运行时参数创建合适的LLM实例。
支持Azure、OpenAI等不同的LLM后端，以及在测试时使用缓存LLM。
"""
import os
from typing import Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

import litellm
from litellm.caching import Cache
from crewai import LLM


def load_llm_config(env_path: Optional[Path] = None) -> Dict[str, str]:
    """加载LLM配置的环境变量
    
    Args:
        env_path: 可选的.env文件路径
        
    Returns:
        包含LLM配置的字典
    """
    if env_path:
        load_dotenv(env_path)

    # 获取所有相关的环境变量
    config = {
        "model": os.getenv("MODEL", "gpt-4o"),
        "api_key": os.getenv("OPENAI_API_KEY"),
        "base_url": os.getenv("OPENAI_BASE_URL"),
        # Azure特定配置
        "azure_api_key": os.getenv("AZURE_API_KEY"),
        "azure_api_base": os.getenv("AZURE_API_BASE"),
        "azure_deployment": os.getenv("AZURE_DEPLOYMENT", "gpt-4o"),
        "azure_deployment_small": os.getenv("AZURE_DEPLOYMENT_SMALL", "gpt-4o-mini"),
        # 测试相关配置
        "testing": os.getenv("TESTING", "false").lower() == "true",
        "use_cache": os.getenv("USE_CACHED_LLM", "false").lower() == "true",
        # 缓存配置
        "cache_type": os.getenv("CACHE_TYPE", "disk"),
        "cache_dir": os.getenv("CACHE_DIR", ".crewai_llm_cache"),
        "cache_ttl": float(os.getenv("CACHE_TTL", "3600"))
    }
    return config


def setup_litellm_cache(config: Dict[str, Any]):
    """配置LiteLLM的缓存
    
    Args:
        config: 配置字典
    """
    if config.get("use_cache"):
        cache_config = {
            "type": config["cache_type"],
            "ttl": config["cache_ttl"]
        }

        # 根据缓存类型添加特定配置
        if config["cache_type"] == "disk":
            cache_config["disk_cache_dir"] = config["cache_dir"]

        # 启用LiteLLM缓存
        litellm.cache = Cache(**cache_config)
        litellm.enable_cache()


def get_llm(
    config: Optional[Dict[str, Any]] = None,
    use_cache: bool = False,
    cache_dir: str = '.crewai_llm_cache',
    **kwargs
) -> LLM:
    """获取配置好的LLM实例
    
    Args:
        config: 可选的配置字典，如果未提供则从环境变量加载
        use_cache: 是否使用缓存LLM
        cache_dir: 缓存目录路径
        **kwargs: 传递给LLM构造函数的额外参数
        
    Returns:
        配置好的LLM实例
    """
    if config is None:
        config = load_llm_config()

    # 合并配置和kwargs
    llm_config = {**kwargs}

    # 确定使用哪个后端
    if config.get("azure_api_key") and config.get("azure_api_base"):
        llm_config.update({
            "model": f"azure/{config['azure_deployment']}",
            "api_key": config["azure_api_key"],
            "base_url": config["azure_api_base"]
        })
    else:
        llm_config.update({
            "model": config["model"],
            "api_key": config["api_key"],
            "base_url": config.get("base_url")  # 可能为None
        })

    # 设置缓存
    if use_cache or config.get("use_cache"):
        config["use_cache"] = True
        config["cache_dir"] = cache_dir
        setup_litellm_cache(config)

    return LLM(**llm_config)

def get_small_llm(
    config: Optional[Dict[str, Any]] = None,
    use_cache: bool = False,
    cache_dir: str = '.crewai_llm_cache',
    **kwargs
) -> LLM:
    """获取配置好的小型LLM实例
    
    此函数类似于get_llm，但使用较小的模型（如gpt-4o-mini）来降低成本或提高响应速度。
    
    Args:
        config: 可选的配置字典，如果未提供则从环境变量加载
        use_cache: 是否使用缓存LLM
        cache_dir: 缓存目录路径
        **kwargs: 传递给LLM构造函数的额外参数
        
    Returns:
        配置好的小型LLM实例
    """
    if config is None:
        config = load_llm_config()

    # 合并配置和kwargs
    llm_config = {**kwargs}

    # 确定使用哪个后端
    if config.get("azure_api_key") and config.get("azure_api_base"):
        llm_config.update({
            "model": f"azure/{config['azure_deployment_small']}",
            "api_key": config["azure_api_key"],
            "base_url": config["azure_api_base"]
        })
    else:
        llm_config.update({
            "model": "gpt-35-turbo",  # 默认使用较小的模型
            "api_key": config["api_key"],
            "base_url": config.get("base_url")  # 可能为None
        })

    # 设置缓存
    if use_cache or config.get("use_cache"):
        config["use_cache"] = True
        config["cache_dir"] = cache_dir
        setup_litellm_cache(config)

    return LLM(**llm_config)
