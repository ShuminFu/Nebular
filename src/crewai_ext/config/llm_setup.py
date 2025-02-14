from pathlib import Path
from src.crewai_ext.config.llm_factory import get_llm, load_llm_config

# 加载环境变量并获取LLM实例
env_path = Path(__file__).parent / ".env"
config = load_llm_config(env_path)
llm = get_llm(config)
