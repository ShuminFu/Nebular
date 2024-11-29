from typing import Dict, Optional, List
from uuid import UUID
from dataclasses import dataclass
import asyncio
import multiprocessing
from crewai import Agent, Task, Crew
from loguru import logger
from Opera.Signalr.opera_signalr_client import OperaSignalRClient, MessageReceivedArgs


@dataclass
class CrewProcessInfo:
    """工作型Crew进程信息"""
    process: multiprocessing.Process
    crew_id: UUID
    opera_id: UUID
    roles: List[str]
    staff_id: Optional[UUID] = None  # 如果作为Staff，则有staff_id


class CrewManager:
    """管理所有工作型Crew的进程"""
    
    def __init__(self):
        self.crew_processes: Dict[UUID, CrewProcessInfo] = {}
        
    async def start_crew_process(self, crew_config: dict, opera_id: UUID) -> UUID:
        """启动新的Crew进程"""
        crew_id = UUID.uuid4()
        
        # 创建进程
        process = multiprocessing.Process(
            target=self._run_crew_process,
            args=(crew_config, opera_id, crew_id)
        )
        
        # 记录进程信息
        self.crew_processes[crew_id] = CrewProcessInfo(
            process=process,
            crew_id=crew_id,
            opera_id=opera_id,
            roles=crew_config.get('roles', [])
        )
        
        # 启动进程
        process.start()
        logger.info(f"已启动Crew进程: {crew_id}")
        
        return crew_id
        
    def _run_crew_process(self, crew_config: dict, opera_id: UUID, crew_id: UUID):
        """在新进程中运行Crew"""
        try:
            # 设置进程级的日志
            logger.add(f"logs/crew_{crew_id}.log")
            
            # 创建和运行Crew
            crew_runner = CrewRunner(crew_config, opera_id, crew_id)
            
            # 运行事件循环
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


class CrewRunner:
    """在独立进程中运行的Crew"""
    
    def __init__(self, config: dict, opera_id: UUID, crew_id: UUID):
        self.config = config
        self.opera_id = opera_id
        self.crew_id = crew_id
        self.client = None
        self.crew = None
        self.is_running = True
        self.reconnect_delay = 5  # 重连延迟秒数
        
    async def setup(self):
        """初始化设置"""
        self.crew = self._setup_crew()
        self.client = OperaSignalRClient()
        
        # 设置SignalR回调
        self.client.set_callback("on_hello", self._handle_hello)
        self.client.set_callback("on_message_received", self._handle_message)
        self.client.set_callback("on_system_shutdown", self._handle_shutdown)
        
    async def run(self):
        """运行Crew的主循环"""
        await self.setup()
        
        while self.is_running:
            try:
                # 建立连接
                await self.client.connect()
                
                # 注册Bot身份
                await self.client.set_bot_id(self.crew_id)
                
                # 如果需要作为Staff身份
                if self.config.get('as_staff', False):
                    await self.client.set_snitch_mode(True)
                    await self._register_as_staff()
                
                # 等待连接关闭
                while self.client.is_connected():
                    await asyncio.sleep(1)
                
                # 如果还在运行但连接断开，则准备重连
                if self.is_running:
                    logger.warning(f"Crew {self.crew_id} 连接断开，{self.reconnect_delay}秒后重连")
                    await asyncio.sleep(self.reconnect_delay)
                    
            except Exception as e:
                logger.exception(f"Crew {self.crew_id} 运行出错: {e}")
                if self.is_running:
                    await asyncio.sleep(self.reconnect_delay)
                    
    async def _handle_hello(self):
        """处理Hello回调"""
        logger.info(f"Crew {self.crew_id} 收到Hello回调，连接成功")
        
    async def _handle_shutdown(self):
        """处理系统关闭信号"""
        logger.info(f"Crew {self.crew_id} 收到系统关闭信号")
        self.is_running = False
        
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
    
    def _setup_crew(self) -> Crew:
        """根据配置设置Crew"""
        agents = []
        tasks = []
        
        # 根据配置创建Agent和Task
        for agent_config in self.config.get('agents', []):
            agent = Agent(
                name=agent_config['name'],
                role=agent_config['role'],
                goal=agent_config['goal'],
                backstory=agent_config['backstory'],
                tools=agent_config.get('tools', [])
            )
            agents.append(agent)
            
            # 为每个Agent创建对应的Task
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
    
    async def _register_as_staff(self):
        """注册为Opera的Staff"""
        # TODO: 实现Staff注册逻辑
        pass
        
    async def _handle_result(self, result: str):
        """处理Crew执行结果"""
        # TODO: 实现结果处理逻辑，例如发送回复消息
        pass