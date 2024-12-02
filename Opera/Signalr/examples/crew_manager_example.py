import asyncio
from uuid import UUID
from typing import Dict, Optional
from Opera.Signalr.opera_signalr_client import OperaSignalRClient, MessageReceivedArgs
from Opera.Signalr.opera_message_processor import CrewManager
from loguru import logger


class BotCrewController:
    """Bot AI Crew控制器"""
    
    def __init__(self, bot_id: str):
        self.bot_id = UUID(bot_id)
        self.client = OperaSignalRClient(bot_id=bot_id)
        self.crew_manager = CrewManager()
        self.bot_crew_id: Optional[UUID] = None  # 当前Bot的Crew ID
        
    async def start(self):
        """启动控制器"""
        # 设置SignalR回调
        self.client.set_callback("on_message_received", self._handle_message)
        
        # 连接SignalR
        await self.client.connect()
        
        # 启动CrewManager
        await self.crew_manager.start()
        
        # 为Bot创建Crew
        crew_config = self._generate_bot_crew_config()
        self.bot_crew_id = await self.crew_manager.start_crew_process(
            crew_config=crew_config,
            opera_id=None  # Bot的Crew不绑定特定Opera
        )
        
        logger.info(f"Bot Crew Controller已启动，Bot ID: {self.bot_id}")
        
    def _generate_bot_crew_config(self) -> dict:
        """生成Bot的Crew配置"""
        return {
            "agents": [
                {
                    "name": "Bot Assistant",
                    "role": "AI助手",
                    "goal": "作为Bot处理来自不同Opera的消息",
                    "backstory": f"我是Bot {self.bot_id}的AI助手",
                    "task": "处理接收到的消息并生成合适的响应"
                }
            ],
            "as_staff": True,
            "process": "sequential"
        }
        
    async def _handle_message(self, message: MessageReceivedArgs):
        """处理接收到的消息"""
        if not self.bot_crew_id:
            logger.error("Bot Crew未初始化")
            return
            
        logger.info(f"收到来自Opera {message.opera_id}的消息: {message.text}")
        
        # 消息会通过CrewManager自动转发给Bot的Crew
        # CrewRunner会在处理消息时获取Opera上下文
        
    async def stop(self):
        """停止控制器"""
        if self.bot_crew_id:
            await self.crew_manager.stop_crew_process(self.bot_crew_id)
        
        await self.client.disconnect()
        logger.info("Bot Crew Controller已停止")


class CrewRunner:
    """在独立进程中运行的Crew（更新版本）"""
    
    def __init__(self, config: dict, opera_id: Optional[UUID], crew_id: UUID):
        self.config = config
        self.opera_id = opera_id  # 可以为None，表示这是Bot的Crew
        self.crew_id = crew_id
        self.client = OperaSignalRClient(bot_id=str(crew_id))
        self.crew = None
        self.is_running = True
        self.opera_contexts: Dict[UUID, dict] = {}  # 存储不同Opera的上下文
        
    async def _handle_message(self, message: MessageReceivedArgs):
        """处理接收到的消息"""
        try:
            # 获取或创建Opera上下文
            context = self.opera_contexts.get(message.opera_id, {
                "messages": [],
                "last_update": None
            })
            
            # 更新上下文
            context["messages"].append({
                "text": message.text,
                "time": message.time,
                "sender": message.sender_staff_id
            })
            context["last_update"] = message.time
            self.opera_contexts[message.opera_id] = context
            
            # 更新Crew任务，包含Opera上下文
            for task in self.crew.tasks:
                task.description = (
                    f"处理来自Opera {message.opera_id}的消息:\n"
                    f"消息内容: {message.text}\n"
                    f"历史上下文: {str(context['messages'][-5:])}\n"  # 最近5条消息
                    f"原始任务: {task.description}"
                )
            
            # 执行Crew任务
            result = await self.crew.kickoff()
            
            # 处理结果
            await self._handle_result(result, message.opera_id)
            
        except Exception as e:
            logger.error(f"消息处理出错: {e}")
    
    async def _handle_result(self, result: str, opera_id: UUID):
        """处理Crew执行结果"""
        try:
            # TODO: 实现发送消息的方法
            # await self.client.send_message(opera_id, result)
            pass
        except Exception as e:
            logger.error(f"结果处理出错: {e}")


async def main():
    # 创建控制器
    bot_id = "894c1763-22b2-418c-9a18-3c40b88d28bc"
    controller = BotCrewController(bot_id)
    
    try:
        # 启动控制器
        await controller.start()
        
        # 保持程序运行
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        await controller.stop()
        logger.info("程序已退出")


if __name__ == "__main__":
    asyncio.run(main()) 