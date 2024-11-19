from bot_manager import BotFactory
from bot_manager.adapters import AutogenBotAdapter

async def main():
    factory = BotFactory()
    factory.register_adapter("autogen", AutogenBotAdapter())
    
    config = {
        "framework": "autogen",
        "bot_type": "user_proxy",
        "name": "code_executor",
        "work_dir": "./workspace",
    }
    
    bot = await factory.create_bot(config)
    return bot 