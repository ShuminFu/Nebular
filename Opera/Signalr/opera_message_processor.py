from typing import Dict, List
from uuid import UUID
from dataclasses import dataclass
import asyncio
import multiprocessing
from crewai import Agent, Task, Crew
from loguru import logger

from Opera.Signalr.opera_signalr_client import OperaSignalRClient, MessageReceivedArgs
from ai_core.tools.bot_api_tool import BotTool
from ai_core.tools.staff_invitation_api_tool import StaffInvitationTool
from ai_core.configs.config import DEFAULT_CREW_MANAGER_PROMPT, CREW_MANAGER_INIT, llm, DEFAULT_CREW_MANAGER


@dataclass
class CrewProcessInfo:
    """工作型Crew进程信息"""
    process: multiprocessing.Process
    bot_id: UUID
    opera_ids: List[UUID]  # 一个Bot可以在多个Opera中
    roles: Dict[UUID, List[str]]  # opera_id -> roles
    staff_ids: Dict[UUID, UUID]  # opera_id -> staff_id


class CrewManager:
    """管理所有工作型Crew的进程"""

    def __init__(self):
        self.bot_id = None
        self.client = None
        # bot_id -> CrewProcessInfo
        self.crew_processes: Dict[UUID, CrewProcessInfo] = {}

    async def start(self):
        """启动CrewManager"""
        # crew 可以直接导入config.py中的Crew，或者对模板字典解包
        crew = Crew(agents=[DEFAULT_CREW_MANAGER], tasks=[Task(**CREW_MANAGER_INIT,agent=DEFAULT_CREW_MANAGER)])
        result = await crew.kickoff()
        self.bot_id = UUID(result['bot_id'])

        # 初始化SignalR客户端
        self.client = OperaSignalRClient(bot_id=str(self.bot_id))
        self.client.set_callback("on_message_received", self._handle_message)
        await self.client.connect()

        logger.info(f"CrewManager已启动，Bot ID: {self.bot_id}")

    async def create_bot_and_crew(self, opera_id: UUID, roles: List[str]) -> UUID:
        """创建新的Bot和对应的Crew"""
        # 这里调用创建Bot的API，获取Bot_ID.
        # 通过Crew生成一份Runner的crew_config,用于后续的进程启动。需要一个生成crew_config的工具以及完善的示例。

    async def start_crew_process(self, crew_config: dict, bot_id: UUID) -> None:
        """启动新的Crew进程"""
        runner = CrewRunner(crew_config, bot_id)
        process = multiprocessing.Process(
            target=runner.run
        )

        self.crew_processes[bot_id] = CrewProcessInfo(
            process=process,
            bot_id=bot_id,
            opera_ids=[],
            roles={},
            staff_ids={}
        )

        process.start()
        logger.info(f"已启动Bot {bot_id}的Crew进程")

    async def _handle_message(self, message: MessageReceivedArgs):
        """处理接收到的消息"""
        # 处理CrewManager自己的消息
        logger.info(f"CrewManager收到消息: {message.text}")
        # 在这里添加处理逻辑，例如更新状态或执行特定操作

    # 处理Bot加入Opera
    async def handle_bot_joined_opera(self, bot_id: UUID, opera_id: UUID, roles: List[str], staff_id: UUID):
        """处理Bot加入新的Opera"""
        if bot_id in self.crew_processes:
            info = self.crew_processes[bot_id]
            info.opera_ids.append(opera_id)
            info.roles[opera_id] = roles
            info.staff_ids[opera_id] = staff_id
            logger.info(f"Bot {bot_id} 已加入 Opera {opera_id}")

    async def stop(self):
        """停止所有Crew进程"""
        for bot_id in list(self.crew_processes.keys()):
            await self.stop_crew_process(bot_id)

        if self.client:
            await self.client.disconnect()
        logger.info("CrewManager已停止")

    async def stop_crew_process(self, bot_id: UUID):
        """停止指定的Crew进程"""
        if bot_id in self.crew_processes:
            info = self.crew_processes[bot_id]
            info.process.terminate()
            info.process.join()
            del self.crew_processes[bot_id]
            logger.info(f"已停止Bot {bot_id}的Crew进程")

    async def _handle_message(self, message: MessageReceivedArgs):
        """处理接收到的消息"""
        for bot_id, info in self.crew_processes.items():
            if message.opera_id in info.opera_ids:
                # 将消息转发给对应的CrewRunner处理
                await self.client.send("ForwardMessage", [str(bot_id), message])


class CrewRunner:
    """在独立进程中运行的Crew"""

    def __init__(self, config: dict, bot_id: UUID):
        self.config = config
        self.bot_id = bot_id
        self.client = OperaSignalRClient(bot_id=str(bot_id))
        self.crew = None
        self.is_running = True

    async def setup(self):
        """初始化设置"""
        self.crew = self._setup_crew()
        await self.client.connect()

        # 设置Staff邀请处理回调
        self.client.set_callback(
            "on_staff_invited", self._handle_staff_invitation)

    async def run(self):
        """运行Crew的主循环"""
        try:
            await self.setup()

            # 设置消息处理回调
            self.client.set_callback(
                "on_message_received", self._handle_message)

            # 保持进程运行
            while self.is_running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.exception(f"Crew运行出错: {e}")
        finally:
            self.is_running = False
            await self.client.disconnect()
            # TODO: 意外错误时，不一定能够执行到这一步。最好是能够用上signalr接收心跳消息来让CrewManager知道是否存活。并且参考signalr的重连

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
                task.description = f"处理消息: {
                    message.text}\n上下文: {task.description}"

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
                    **DEFAULT_CREW_MANAGER_PROMPT,  # 继承基础配置
                    "name": "Bot Creator",
                    "tools": [BotTool()],
                }
            ],
            "tasks": [
                {
                    **CREW_MANAGER_INIT,  # 继承基础任务配置
                    "description": "创建一个新的Bot实例并返回其ID"
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
                        StaffInvitationTool()  # 添加Staff邀请工具
                    ],
                    "task": "监控和响应Opera中的事件，确保正确处理所有消息"
                }
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
                llm=llm,  # 使用统一的LLM配置
                **agent_config
            )
            agents.append(agent)

        for task_config in config['tasks']:
            task = Task(
                agent=agents[0],  # 假设只有一个agent
                **task_config
            )
            tasks.append(task)

        return Crew(
            agents=agents,
            tasks=tasks,
            process=config['process']
        )

    async def _handle_staff_invitation(self, invitation_data: dict):
        """处理Staff邀请"""
        # TODO 这里改为无脑接受邀请
        logger.info(f"Bot {self.bot_id} 已处理Opera {
                    invitation_data['opera_id']}的Staff邀请")
