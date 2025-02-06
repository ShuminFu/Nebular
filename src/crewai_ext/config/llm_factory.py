"""LLM工厂模块，提供动态LLM配置和实例化功能。

此模块负责根据环境变量和运行时参数创建合适的LLM实例。
支持Azure、OpenAI等不同的LLM后端，以及在测试时使用缓存LLM。
"""
import os
from typing import Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

from crewai import LLM
from src.crewai_ext.tools.cached_llm import CachedLLM, crewai_llm_cache


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
        # 测试相关配置
        "testing": os.getenv("TESTING", "false").lower() == "true",
        "use_cache": os.getenv("USE_CACHED_LLM", "false").lower() == "true"
    }
    return config


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

    # 在测试模式或显式要求时使用缓存
    if config.get("testing") or use_cache or config.get("use_cache"):
        return CachedLLM(
            cache=crewai_llm_cache,
            cache_dir=cache_dir,
            **llm_config
        )

    return LLM(**llm_config)
