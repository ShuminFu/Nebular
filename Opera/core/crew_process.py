from typing import Dict, List, Optional
from uuid import UUID
from dataclasses import dataclass
import asyncio
import multiprocessing
from abc import ABC, abstractmethod
from crewai import Agent, Task, Crew
from Opera.core.logger_config import get_logger, get_logger_with_trace_id

from Opera.signalr_client.opera_signalr_client import OperaSignalRClient, MessageReceivedArgs
from ai_core.configs.config import CREW_MANAGER_INIT, DEFAULT_CREW_MANAGER
from ai_core.configs.base_agents import create_intent_agent, create_persona_agent
from Opera.core.intent_mind import IntentMind
from Opera.core.task_utils import BotTaskQueue, TaskType, TaskStatus


@dataclass
class CrewProcessInfo:
    """工作型Crew进程信息"""
    process: multiprocessing.Process
    bot_id: UUID
    opera_ids: List[UUID]  # 一个Bot可以在多个Opera中
    roles: Dict[UUID, List[str]]  # opera_id -> roles
    staff_ids: Dict[UUID, UUID]  # opera_id -> staff_id


class BaseCrewProcess(ABC):
    """Crew进程的基类，定义共同的接口和功能"""

    def __init__(self):
        self.bot_id: Optional[UUID] = None
        self.client: Optional[OperaSignalRClient] = None
        self.is_running: bool = True
        self.crew: Optional[Crew] = None
        self.intent_agent: Optional[Agent] = None
        self.persona_agent: Optional[Agent] = None
        # 为每个进程创建一个带trace_id的logger
        self.log = get_logger_with_trace_id()

    async def setup(self):
        """初始化设置"""
        self.intent_agent = create_intent_agent()
        self.persona_agent = create_persona_agent()

        self.task_queue = BotTaskQueue(bot_id=self.bot_id)
        self.intent_processor = IntentMind(self.task_queue)

        # 设置Crew
        self.crew = self._setup_crew()

        if self.bot_id:
            self.client = OperaSignalRClient(bot_id=str(self.bot_id))
            self.client.set_callback("on_hello", self._handle_hello)
            await self.client.connect()

            # 等待连接建立
            for _ in range(30):  # 30秒超时
                if self.client._connected:
                    self.log.info(f"{self.__class__.__name__} 进程准备就绪")
                    break
                await asyncio.sleep(1)
            else:
                self.log.error(f"等待{self.__class__.__name__} SignalR连接超时")
                raise asyncio.TimeoutError()

            self.client.set_callback(
                "on_message_received", self._handle_message)

    async def stop(self):
        """停止Crew运行"""
        self.is_running = False
        if self.client:
            await self.client.disconnect()

    async def run(self):
        """运行Crew的主循环"""
        try:
            await self.setup()
            while self.is_running:
                # 检查连接状态
                if self.client and not self.client._connected:
                    self.log.warning("检测到连接断开，尝试重新连接")
                    await self.setup()
                    continue

                # 处理任务队列中的任务
                task = self.task_queue.get_next_task()
                if task:
                    await self._process_task(task)
                await asyncio.sleep(1)
        except Exception as e:
            self.log.exception(f"Crew运行出错: {e}")
        finally:
            await self.stop()

    async def _handle_hello(self):
        """处理hello消息"""
        self.log.info(f"{self.__class__.__name__}SignalR连接已建立")

    async def _process_task(self, task):
        """处理任务队列中的任务"""
        try:
            # 根据任务类型执行不同的处理逻辑
            if task.type == TaskType.CONVERSATION:
                await self._handle_conversation_task(task)
            elif task.type == TaskType.ACTION:
                await self._handle_action_task(task)
            elif task.type == TaskType.ANALYSIS:
                await self._handle_analysis_task(task)
        except Exception as e:
            self.log.exception(f"处理任务出错: {e}")
            task.status = TaskStatus.FAILED
        else:
            task.status = TaskStatus.COMPLETED

    async def _handle_message(self, message: MessageReceivedArgs):
        """处理接收到的消息"""
        self.log.info(f"收到消息: {message.text}")
        # 使用意图处理器处理消息，直接生成任务到共享的任务队列中
        await self.intent_processor.process_message(message)

    @abstractmethod
    def _setup_crew(self) -> Crew:
        """设置Crew配置，由子类实现"""
        pass

    @abstractmethod
    async def _handle_conversation_task(self, task):
        """处理对话类型的任务"""
        pass

    @abstractmethod
    async def _handle_action_task(self, task):
        """处理动作类型的任务"""
        pass

    @abstractmethod
    async def _handle_analysis_task(self, task):
        """处理分析类型的任务"""
        pass


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

    async def _handle_conversation_task(self, task):
        """处理对话类型的任务"""
        # 实现CrewManager特定的对话任务处理逻辑
        pass

    async def _handle_action_task(self, task):
        """处理动作类型的任务"""
        # 实现CrewManager特定的动作任务处理逻辑
        pass

    async def _handle_analysis_task(self, task):
        """处理分析类型的任务"""
        # 实现CrewManager特定的分析任务处理逻辑
        pass


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

    async def _handle_action_task(self, task):
        """处理动作类型的任务"""
        # 实现CrewRunner特定的动作任务处理逻辑
        pass

    async def _handle_analysis_task(self, task):
        """处理分析类型的任务"""
        # 实现CrewRunner特定的分析任务处理逻辑
        pass

    async def _handle_conversation_task(self, task):
        """处理对话类型的任务"""
        # 实现CrewRunner特定的对话任务处理逻辑
        pass
