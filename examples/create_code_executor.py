from bot_manager.core.factory import BotFactory
from bot_manager.adapters.autogen_adapter import AutogenBotAdapter

async def create_code_executor():
    factory = BotFactory()
    factory.register_adapter("autogen", AutogenBotAdapter())
    
    config = {
        "framework": "autogen",
        "bot_type": "user_proxy",
        "name": "code_executor",
        "work_dir": "./workspace",
        "use_docker": False,
        "max_consecutive_auto_reply": 5
    }

    executor_bot = await factory.create_bot(config)
    return executor_bot

# 使用示例
async def main():
    executor_bot = await create_code_executor()
    
    # 执行代码
    result = await executor_bot.invoke_capability(
        "code_execution",
        code="print('Hello, World!')",
        language="python"
    )
    print(result) 