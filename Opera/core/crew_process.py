from typing import Dict, List, Optional
from uuid import UUID
from dataclasses import dataclass
import asyncio
import multiprocessing
from abc import ABC, abstractmethod
from crewai import Agent, Task, Crew
from loguru import logger

from Opera.signalr_client.opera_signalr_client import OperaSignalRClient, MessageReceivedArgs
from ai_core.configs.config import CREW_MANAGER_INIT, DEFAULT_CREW_MANAGER
from ai_core.configs.base_agents import create_intent_mind_agent, create_persona_switch_agent

class BaseCrewProcess(ABC):
    """Crew进程的基类，定义共同的接口和功能"""

    def __init__(self):
        self.bot_id: Optional[UUID] = None
        self.client: Optional[OperaSignalRClient] = None
        self.is_running: bool = True
        self.crew: Optional[Crew] = None
        self._connection_established = asyncio.Event()
        self.intent_mind: Optional[Agent] = None
        self.persona_switch: Optional[Agent] = None

    async def setup(self):
        """初始化设置"""
        # 初始化基础Agent
        self.intent_mind = create_intent_mind_agent()
        self.persona_switch = create_persona_switch_agent()
        
        # 设置Crew
        self.crew = self._setup_crew()
        
        if self.bot_id:
            self.client = OperaSignalRClient(bot_id=str(self.bot_id))
            self.client.set_callback("on_hello", self._handle_hello)
            await self.client.connect()
            self.client.set_callback("on_message_received", self._handle_message)
            try:
                await asyncio.wait_for(self._connection_established.wait(), timeout=30)
                logger.info(f"{self.__class__.__name__} SignalR连接已成功建立")
            except asyncio.TimeoutError:
                logger.error(f"等待{self.__class__.__name__} SignalR连接超时")
                raise

    async def _handle_hello(self):
        """处理hello消息"""
        logger.info(f"{self.__class__.__name__}收到hello消息，连接已建立")
        self._connection_established.set()

    async def stop(self):
        """停止Crew运行"""
        self._connection_established.clear()  # 清除连接状态
        self.is_running = False
        if self.client:
            await self.client.disconnect()

    async def run(self):
        """运行Crew的主循环"""
        try:
            await self.setup()
            while self.is_running:
                await asyncio.sleep(1)
        except Exception as e:
            logger.exception(f"Crew运行出错: {e}")
        finally:
            await self.stop()

    @abstractmethod
    def _setup_crew(self) -> Crew:
        """设置Crew配置，由子类实现"""
        pass

    @abstractmethod
    async def _handle_message(self, message: MessageReceivedArgs):
        """处理接收到的消息，由子类实现"""
        pass

    async def _process_message_with_intent_mind(self, message: MessageReceivedArgs):
        """使用IntentMind处理消息"""
        # 创建任务
        task = Task(
            description=f"Analyze the intent of the message: {message.text}",
            agent=self.intent_mind
        )
        return await self.crew.run_async([task])

    async def _process_result_with_persona_switch(self, result: str, staff_id: UUID):
        """使用PersonaSwitch处理结果"""
        task = Task(
            description=f"Process the result and respond as staff {staff_id}: {result}",
            agent=self.persona_switch
        )
        return await self.crew.run_async([task])

@dataclass
class CrewProcessInfo:
    """工作型Crew进程信息"""
    process: multiprocessing.Process
    bot_id: UUID
    opera_ids: List[UUID]  # 一个Bot可以在多个Opera中
    roles: Dict[UUID, List[str]]  # opera_id -> roles
    staff_ids: Dict[UUID, UUID]  # opera_id -> staff_id

class CrewManager(BaseCrewProcess):
    """管理所有工作型Crew的进程"""

    def __init__(self):
        super().__init__()
        self.crew_processes: Dict[UUID, CrewProcessInfo] = {}

    def _setup_crew(self) -> Crew:
        return Crew(
            agents=[DEFAULT_CREW_MANAGER], 
            tasks=[Task(**CREW_MANAGER_INIT, agent=DEFAULT_CREW_MANAGER)]
        )

    async def start(self):
        """开始处理CrewManager的Task队列等逻辑"""
        pass

    async def _handle_message(self, message: MessageReceivedArgs):
        """处理接收到的消息"""
        logger.info(f"收到消息: {message.text}")

class CrewRunner(BaseCrewProcess):
    """在独立进程中运行的Crew"""

    def __init__(self, config: dict, bot_id: UUID):
        super().__init__()
        self.config = config
        self.bot_id = bot_id

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
        logger.info(f"收到消息: {message.text}")

    async def _handle_result(self, result: str):
        """处理Crew执行结果"""
        # TODO: 实现结果处理逻辑，例如进行后续的任务，更新Staff的Parameters等等。
        pass

