from typing import Dict, Optional, List
from uuid import UUID
from dataclasses import dataclass
import asyncio
import multiprocessing
from crewai import Agent, Task, Crew
from loguru import logger
from datetime import datetime

from Opera.Signalr.opera_signalr_client import OperaSignalRClient, MessageReceivedArgs


@dataclass
class CrewProcessInfo:
    """工作型Crew进程信息"""
    process: multiprocessing.Process
    crew_id: UUID
    opera_id: UUID
    roles: List[str]
    staff_id: Optional[UUID] = None


class CrewManager:
    """管理所有工作型Crew的进程"""
    
    def __init__(self):
        self.crew_processes: Dict[UUID, CrewProcessInfo] = {}
        self.client = OperaSignalRClient()
        
    async def start(self):
        """启动CrewManager"""
        # 设置消息处理回调
        self.client.set_callback("on_message_received", self._handle_message)
        await self.client.connect()
        
    async def start_crew_process(self, crew_config: dict, opera_id: UUID) -> UUID:
        """启动新的Crew进程"""
        crew_id = UUID.uuid4()
        
        process = multiprocessing.Process(
            target=self._run_crew_process,
            args=(crew_config, opera_id, crew_id)
        )
        
        self.crew_processes[crew_id] = CrewProcessInfo(
            process=process,
            crew_id=crew_id,
            opera_id=opera_id,
            roles=crew_config.get('roles', [])
        )
        
        process.start()
        logger.info(f"已启动Crew进程: {crew_id}")
        
        return crew_id
        
    def _run_crew_process(self, crew_config: dict, opera_id: UUID, crew_id: UUID):
        """在新进程中运行Crew"""
        try:
            logger.add(f"logs/crew_{crew_id}.log")
            crew_runner = CrewRunner(crew_config, opera_id, crew_id)
            asyncio.run(crew_runner.run())
        except Exception as e:
            logger.exception(f"Crew进程运行出错: {e}")
        finally:
            logger.info(f"Crew进程 {crew_id} 已退出")
            
    async def stop_crew_process(self, crew_id: UUID):
        """停止指定的Crew进程"""
        if crew_id in self.crew_processes:
            info = self.crew_processes[crew_id]
            info.process.terminate()
            info.process.join()
            del self.crew_processes[crew_id]
            logger.info(f"已停止Crew进程: {crew_id}")
            
    async def _handle_message(self, message: MessageReceivedArgs):
        """处理接收到的消息，分发给相应的Crew"""
        for crew_id, info in self.crew_processes.items():
            if info.opera_id == message.opera_id:
                # 将消息转换为Crew任务
                await self._update_crew_tasks(crew_id, message)


class CrewRunner:
    """在独立进程中运行的Crew"""
    
    def __init__(self, config: dict, opera_id: UUID, crew_id: UUID):
        self.config = config
        self.opera_id = opera_id
        self.crew_id = crew_id
        self.client = OperaSignalRClient(bot_id=str(crew_id))
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
