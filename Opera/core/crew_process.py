from typing import Dict, List, Optional
from uuid import UUID
from dataclasses import dataclass
import asyncio
import multiprocessing
from abc import ABC, abstractmethod
from crewai import Agent, Task, Crew
from Opera.FastAPI.models import BotForUpdate, DialogueForCreation
from Opera.core.logger_config import get_logger_with_trace_id
from Opera.core.api_response_parser import ApiResponseParser
from Opera.signalr_client.opera_signalr_client import OperaSignalRClient, MessageReceivedArgs
from ai_core.configs.config import CREW_MANAGER_INIT, DEFAULT_CREW_MANAGER
from ai_core.configs.base_agents import create_intent_agent, create_persona_agent
from ai_core.tools.opera_api.bot_api_tool import _SHARED_BOT_TOOL
from ai_core.tools.opera_api.dialogue_api_tool import _SHARED_DIALOGUE_TOOL
from Opera.core.intent_mind import IntentMind
from Opera.core.task_utils import BotTaskQueue, TaskType, TaskStatus, BotTask, PersistentTaskState, TaskPriority

import json


@dataclass
class CrewProcessInfo:
    """工作型Crew进程信息"""
    process: multiprocessing.Process
    bot_id: UUID
    opera_ids: List[UUID]  # 一个Bot可以在多个Opera中
    roles: Dict[UUID, List[str]]  # opera_id -> roles
    staff_ids: Dict[UUID, List[UUID]]  # opera_id -> staff_ids


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

    async def _process_task(self, task: BotTask):
        """处理任务队列中的任务"""
        try:
            # 根据任务类型执行不同的处理逻辑
            if task.type == TaskType.CONVERSATION:
                await self._handle_conversation_task(task)
            elif task.type == TaskType.ACTION:
                await self._handle_action_task(task)
            elif task.type == TaskType.ANALYSIS:
                await self._handle_analysis_task(task)
            elif task.type == TaskType.CALLBACK:
                await self._handle_task_callback(task)
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
    async def _handle_conversation_task(self, task: BotTask):
        """处理对话类型的任务"""
        pass

    @abstractmethod
    async def _handle_action_task(self, task: BotTask):
        """处理动作类型的任务"""
        pass

    @abstractmethod
    async def _handle_analysis_task(self, task: BotTask):
        """处理分析类型的任务"""
        pass

    async def _handle_task_callback(self, task: BotTask):
        """处理任务回调"""
        pass


class CrewManager(BaseCrewProcess):
    """管理所有工作型Crew的进程"""

    def __init__(self):
        super().__init__()
        self.crew_processes: Dict[UUID, CrewProcessInfo] = {}
        self._staff_id_cache: Dict[str, UUID] = {}  # opera_id -> staff_id 的缓存

    async def _get_cm_staff_id(self, opera_id: str) -> Optional[UUID]:
        """获取CrewManager在指定Opera中的staff_id
        
        Args:
            opera_id: Opera的ID
            
        Returns:
            Optional[UUID]: 如果找到则返回staff_id，否则返回None
        """
        # 先检查缓存
        cache_key = str(opera_id)
        if cache_key in self._staff_id_cache:
            return self._staff_id_cache[cache_key]

        try:
            # 使用bot_api_tool获取Bot的所有Staff信息
            result = _SHARED_BOT_TOOL.run(
                action="get_all_staffs",
                bot_id=self.bot_id,
                data={
                    "need_opera_info": True,
                    "need_staffs": 1,
                    "need_staff_invitations": 0
                }
            )

            # 解析API响应
            status_code, data = ApiResponseParser.parse_response(result)
            if status_code != 200 or not data:
                self.log.error(f"获取Bot {self.bot_id} 的Staff信息失败")
                return None

            # 遍历所有Opera的Staff信息
            for opera_info in data:
                if str(opera_info.get("operaId")) == str(opera_id):
                    staffs = opera_info.get("staffs", [])
                    if staffs:
                        # 找到第一个属于这个Bot的Staff
                        staff_id = UUID(staffs[0].get("id"))
                        # 缓存结果
                        self._staff_id_cache[cache_key] = staff_id
                        return staff_id

            self.log.error(f"在Opera {opera_id} 中未找到Bot {self.bot_id} 的Staff")
            return None

        except Exception as e:
            self.log.error(f"获取CM的staff_id时发生错误: {str(e)}")
            return None

    def _setup_crew(self) -> Crew:
        return Crew(
            agents=[DEFAULT_CREW_MANAGER],
            tasks=[Task(**CREW_MANAGER_INIT, agent=DEFAULT_CREW_MANAGER)]
        )

    async def _handle_conversation_task(self, task: BotTask):
        """处理对话类型的任务"""
        # 实现CrewManager特定的对话任务处理逻辑
        pass

    async def _handle_action_task(self, task: BotTask):
        """处理动作类型的任务"""
        # 实现CrewManager特定的动作任务处理逻辑
        pass

    async def _handle_analysis_task(self, task: BotTask):
        """处理分析类型的任务"""
        # 实现CrewManager特定的分析任务处理逻辑
        pass

    async def _process_task(self, task: BotTask):
        # 检查任务是否需要由CR执行
        if task.response_staff_id in self.crew_processes:
            # 获取对应的CR进程
            cr_process = self.crew_processes[task.response_staff_id]
            # 更新CR的任务队列
            await self._update_cr_task_queue(cr_process.bot_id, task)
        else:
            # CM自己处理的任务
            await super()._process_task(task)

    async def _update_cr_task_queue(self, cr_bot_id: UUID, task: BotTask):
        """更新CrewRunner的任务队列"""
        try:
            # 获取opera_id
            opera_id = task.parameters.get("opera_id")
            if not opera_id:
                self.log.error("任务缺少opera_id参数")
                return

            # 获取CM的staff_id
            cm_staff_id = await self._get_cm_staff_id(opera_id)
            if not cm_staff_id:
                self.log.error(f"无法获取CM在Opera {opera_id} 中的staff_id")
                return

            # 更新任务的source_staff_id
            task_data = task.model_dump(by_alias=True)
            task_data["sourceStaffId"] = str(cm_staff_id)

            # 使用Bot API更新CR的DefaultTags
            result = _SHARED_BOT_TOOL.run(
                action="update",
                bot_id=cr_bot_id,
                data=BotForUpdate(
                    name=None,
                    is_description_updated=False,
                    description=None,
                    is_call_shell_on_opera_started_updated=False,
                    call_shell_on_opera_started=None,
                    is_default_tags_updated=True,
                    default_tags=json.dumps({
                        "TaskStates": [
                            PersistentTaskState.from_bot_task(task).model_dump(by_alias=True)
                        ]
                    }),
                    is_default_roles_updated=False,
                    default_roles=None,
                    is_default_permissions_updated=False,
                    default_permissions=None
                )
            )

            # 检查更新结果
            status_code, _ = ApiResponseParser.parse_response(result)
            if status_code not in [200, 204]:
                self.log.error(f"更新CrewRunner {cr_bot_id} 的任务队列失败")
        except Exception as e:
            self.log.error(f"更新CrewRunner任务队列时发生错误: {str(e)}")

    async def _handle_task_callback(self, task: BotTask):
        """处理来自CR的任务回调"""
        try:
            # 从任务参数中获取回调信息
            task_id = task.parameters.get("callback_task_id")
            result = task.parameters.get("result")

            if not task_id:
                raise ValueError("回调任务缺少task_id参数")

            # 更新原始任务的状态
            await self.task_queue.update_task_status(
                task_id=UUID(task_id),
                new_status=TaskStatus.COMPLETED
            )

            # 记录日志
            self.log.info(f"任务 {task_id} 已完成，结果: {result}")

        except Exception as e:
            self.log.error(f"处理任务回调时发生错误: {str(e)}")
            raise


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

    async def _handle_action_task(self, task: BotTask):
        """处理动作类型的任务"""
        # 实现CrewRunner特定的动作任务处理逻辑
        pass

    async def _handle_analysis_task(self, task: BotTask):
        """处理分析类型的任务"""
        # 实现CrewRunner特定的分析任务处理逻辑
        pass

    async def _handle_conversation_task(self, task: BotTask):
        """处理对话类型的任务"""
        # 实现CrewRunner特定的对话任务处理逻辑
        pass

    async def _handle_task_completion(self, task: BotTask, result: str):
        """处理任务完成后的回调"""
        try:
            # 使用dialogue_api_tool创建回调消息
            callback_result = _SHARED_DIALOGUE_TOOL.run(
                action="create",
                opera_id=task.parameters.get("opera_id"),
                data=DialogueForCreation(
                    is_stage_index_null=False,
                    staff_id=str(task.source_staff_id),
                    is_narratage=False,
                    is_whisper=True,
                    text=json.dumps({
                        "type": TaskType.CALLBACK.value,
                        "priority": TaskPriority.URGENT.value,
                        "description": f"Callback for task {task.id}",
                        "parameters": {
                            "callback_task_id": str(task.id),
                            "result": result,
                            "opera_id": task.parameters.get("opera_id")
                        }
                    }),
                    tags="task_callback",
                    mentioned_staff_ids=[str(task.source_staff_id)]
                )
            )

            # 检查回调消息是否创建成功
            status_code, _ = ApiResponseParser.parse_response(callback_result)
            if status_code not in [200, 204, 201]:
                self.log.error(f"创建任务回调消息失败: {callback_result}")

        except Exception as e:
            self.log.error(f"发送任务回调时发生错误: {str(e)}")
