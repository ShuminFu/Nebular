from typing import Dict, Optional, List
from uuid import UUID
from dataclasses import dataclass
import asyncio
import multiprocessing
from crewai import Agent, Task, Crew
from loguru import logger
from datetime import datetime

from Opera.Signalr.opera_signalr_client import OperaSignalRClient, MessageReceivedArgs
from ai_core.tools.bot_api_tool import BotTool


@dataclass
class CrewProcessInfo:
    """工作型Crew进程信息"""
    process: multiprocessing.Process
    opera_id: UUID
    roles: List[str]
    staff_id: Optional[UUID] = None


class CrewManager:
    """管理所有工作型Crew的进程"""
    
    def __init__(self):
        self.bot_id = None
        self.client = None
        self.crew_processes: Dict[UUID, CrewProcessInfo] = {}
        
    async def start(self):
        """启动CrewManager"""
        # 创建初始Crew来获取Bot ID
        init_crew_config = self._generate_init_crew_config()
        crew = self._setup_init_crew(init_crew_config)
        
        # 执行获取Bot ID的任务
        result = await crew.kickoff()
        self.bot_id = UUID(result['bot_id'])
        
        # 初始化SignalR客户端
        self.client = OperaSignalRClient(bot_id=str(self.bot_id))
        self.client.set_callback("on_message_received", self._handle_message)
        await self.client.connect()
        
        # 为Bot创建Crew
        crew_config = self._generate_bot_crew_config()
        await self.start_crew_process(
            crew_config=crew_config,
            opera_id=None  # Bot的Crew不绑定特定Opera
        )
        
        logger.info(f"CrewManager已启动，Bot ID: {self.bot_id}")
        
    async def start_crew_process(self, crew_config: dict, opera_id: Optional[UUID]) -> None:
        """启动新的Crew进程"""
        process = multiprocessing.Process(
            target=self._run_crew_process,
            args=(crew_config, opera_id, self.bot_id)
        )
        
        if opera_id:  # 只有Opera相关的Crew需要记录
            self.crew_processes[opera_id] = CrewProcessInfo(
                process=process,
                opera_id=opera_id,
                roles=crew_config.get('roles', [])
            )
        
        process.start()
        logger.info(f"已启动{'Opera ' + str(opera_id) if opera_id else 'Bot'} 的Crew进程")
        
    async def stop(self):
        """停止所有Crew进程"""
        for opera_id in list(self.crew_processes.keys()):
            await self.stop_crew_process(opera_id)
        
        if self.client:
            await self.client.disconnect()
        logger.info("CrewManager已停止")
        
    async def stop_crew_process(self, opera_id: UUID):
        """停止指定的Crew进程"""
        if opera_id in self.crew_processes:
            info = self.crew_processes[opera_id]
            info.process.terminate()
            info.process.join()
            del self.crew_processes[opera_id]
            logger.info(f"已停止Opera {opera_id}的Crew进程")
            
    async def _handle_message(self, message: MessageReceivedArgs):
        """处理接收到的消息，分发给相应的Crew"""
        for opera_id, info in self.crew_processes.items():
            if info.opera_id == message.opera_id:
                # 将消息转换为Crew任务
                await self._update_crew_tasks(opera_id, message)


class CrewRunner:
    """在独立进程中运行的Crew"""
    
    def __init__(self, config: dict, opera_id: UUID, bot_id: UUID):
        self.config = config
        self.opera_id = opera_id
        self.bot_id = bot_id
        self.client = OperaSignalRClient(bot_id=str(bot_id))
        self.crew = None
        self.is_running = True
        
    async def setup(self):
        """初始化设置"""
        self.crew = self._setup_crew()
        await self.client.connect()
        
        if self.config.get('as_staff', False):
            await self.client.set_snitch_mode(True)
            await self._register_as_staff()
    
    async def run(self):
        """运行Crew的主循环"""
        try:
            await self.setup()
            
            # 设置消息处理回调
            self.client.set_callback("on_message_received", self._handle_message)
            
            # 保持进程运行
            while self.is_running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.exception(f"Crew运行出错: {e}")
        finally:
            self.is_running = False
            await self.client.disconnect()
    
    def _setup_crew(self) -> Crew:
        """根据配置设置Crew"""
        agents = []
        tasks = []
        
        for agent_config in self.config.get('agents', []):
            agent = Agent(
                name=agent_config['name'],
                role=agent_config['role'],
                goal=agent_config['goal'],
                backstory=agent_config['backstory'],
                tools=agent_config.get('tools', [])
            )
            agents.append(agent)
            
            if 'task' in agent_config:
                task = Task(
                    description=agent_config['task'],
                    agent=agent
                )
                tasks.append(task)
        
        return Crew(
            agents=agents,
            tasks=tasks,
            process=self.config.get('process', 'sequential'),
            verbose=True
        )
        
    async def _handle_message(self, message: MessageReceivedArgs):
        """处理接收到的消息"""
        try:
            # 更新Crew任务
            for task in self.crew.tasks:
                task.description = f"处理消息: {message.text}\n上下文: {task.description}"
            
            # 执行Crew任务
            result = await self.crew.kickoff()
            
            # 处理结果
            await self._handle_result(result)
            
        except Exception as e:
            logger.error(f"消息处理出错: {e}")
            
    async def stop(self):
        """停止Crew运行"""
        self.is_running = False
        if self.client:
            await self.client.disconnect()
    
    async def _handle_result(self, result: str):
        """处理Crew执行结果"""
        # TODO: 实现结果处理逻辑，例如发送回复消息
        pass

    def _generate_init_crew_config(self) -> dict:
        """生成初始化Crew的配置"""
        return {
            "agents": [
                {
                    "name": "Bot Creator",
                    "role": "系统初始化专家",
                    "goal": "创建新的Bot实例",
                    "backstory": "我负责创建和初始化新的Bot实例",
                    "tools": [BotTool()],  # 添加创建Bot的Tool
                    "task": "创建一个新的Bot实例并返回其ID"
                }
            ],
            "process": "sequential"
        }

    def _generate_bot_crew_config(self) -> dict:
        """生成Bot的主Crew配置"""
        return {
            "agents": [
                {
                    "name": "Opera Manager",
                    "role": "Opera管理专家",
                    "goal": "管理和响应Opera中的事件和消息",
                    "backstory": "我是一个专业的Opera管理者，负责处理各种Opera相关的事件和消息",
                    "tools": [
                        # 这里可以添加需要的工具，比如：
                        # - 消息发送工具
                        # - Opera状态查询工具
                        # - 角色管理工具等
                    ],
                    "task": "监控和响应Opera中的事件，确保正确处理所有消息"
                }
                # 可以根据需要添加更多Agent
            ],
            "process": "sequential",
            "verbose": True
        }

    def _setup_init_crew(self, config: dict) -> Crew:
        """设置初始化Crew"""
        agents = []
        tasks = []
        
        for agent_config in config['agents']:
            agent = Agent(
                name=agent_config['name'],
                role=agent_config['role'],
                goal=agent_config['goal'],
                backstory=agent_config['backstory'],
                tools=agent_config['tools']
            )
            agents.append(agent)
            
            task = Task(
                description=agent_config['task'],
                agent=agent
            )
            tasks.append(task)
        
        return Crew(
            agents=agents,
            tasks=tasks,
            process=config['process']
        )
