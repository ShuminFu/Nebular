from typing import Dict, List, Optional
from uuid import UUID
from dataclasses import dataclass
import asyncio
import multiprocessing
from abc import ABC, abstractmethod
from crewai import Agent, Task, Crew
from src.opera_service.api.models import BotForUpdate, DialogueForCreation
from src.core.logger_config import get_logger_with_trace_id
from src.core.api_response_parser import ApiResponseParser
from src.opera_service.signalr_client.opera_signalr_client import OperaSignalRClient, MessageReceivedArgs
from src.crewai_ext.config.llm_setup import CREW_MANAGER_INIT, DEFAULT_CREW_MANAGER
from src.crewai_ext.tools.opera_api.bot_api_tool import _SHARED_BOT_TOOL
from src.crewai_ext.tools.opera_api.dialogue_api_tool import _SHARED_DIALOGUE_TOOL
from src.core.intent_mind import IntentMind
from src.core.task_utils import BotTaskQueue, TaskType, TaskStatus, BotTask, PersistentTaskState, TaskPriority
from src.core.code_monkey import CodeMonkey
from src.core.topic.topic_tracker import TopicTracker

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
        # self.intent_agent = create_intent_agent() # 无实际用途，占位
        # self.persona_agent = create_persona_agent()  # 无实际用途，占位

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

            self.client.set_callback("on_message_received", self._handle_message)

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
                task = await self.task_queue.get_next_task()
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
            elif task.type == TaskType.RESOURCE_GENERATION:
                await self._handle_generation_task(task)
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
    async def _handle_generation_task(self, task: BotTask):
        """处理生成类型的任务"""
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

        # 初始化主题追踪器
        self.topic_tracker = TopicTracker()
        # 注册主题完成回调
        self.topic_tracker.on_completion(self._handle_topic_completed)

    async def setup(self):
        """初始化设置"""
        await super().setup()
        # 创建资源处理器
        self.resource_handler = CodeMonkey(self.task_queue, self.log)

        # 设置任务状态变更回调
        self.task_queue.add_status_callback(self._handle_task_status_changed)

    async def _handle_task_status_changed(self, task_id: UUID, new_status: TaskStatus):
        """处理任务状态变更"""
        # 更新主题追踪器
        await self.topic_tracker.update_task_status(task_id, new_status)

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
                action="get_all_staffs", bot_id=self.bot_id, data={"need_opera_info": True, "need_staffs": 1, "need_staff_invitations": 0}
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
        return Crew(agents=[DEFAULT_CREW_MANAGER], tasks=[Task(**CREW_MANAGER_INIT, agent=DEFAULT_CREW_MANAGER)])

    async def _handle_conversation_task(self, task: BotTask):
        """处理对话类型的任务"""
        # 实现CrewManager特定的对话任务处理逻辑
        pass

    async def _handle_generation_task(self, task: BotTask):
        """处理动作类型的任务"""
        # 实现CrewManager特定的动作任务处理逻辑
        pass

    async def _handle_analysis_task(self, task: BotTask):
        """处理分析类型的任务"""
        # 实现CrewManager特定的分析任务处理逻辑
        pass

    async def _handle_code_generation(self, task: BotTask):
        """处理单个代码生成任务"""
        try:
            # 创建代码生成Agent
            code_gen_agent = Agent(
                name="代码生成专家",
                role="专业程序员",
                goal=f"生成{task.parameters['file_type']}代码文件",
                backstory=f"""你是一个专业的程序员，专注于生成高质量的{task.parameters["file_type"]}代码。
                你需要理解整个项目的上下文，但只负责生成{task.parameters["file_path"]}文件。
                要考虑文件之间的引用关系：{task.parameters.get("references", [])}""",
            )

            # 创建代码生成任务
            task_desc = f"""根据以下信息生成代码：
                1. 文件路径：{task.parameters["file_path"]}
                2. 文件类型：{task.parameters["file_type"]}
                3. 需求描述：{task.parameters["dialogue_context"]["text"]}
                4. 项目信息：
                   - 类型：{task.parameters["code_details"]["project_type"]}
                   - 描述：{task.parameters["code_details"]["project_description"]}
                   - 框架：{task.parameters["code_details"]["frameworks"]}
                5. 相关文件：{task.parameters["code_details"]["resources"]}
                6. 引用关系：{task.parameters.get("references", [])}

                请生成符合要求的代码内容。
                """

            # 记录LLM输入
            self.log.info(f"[LLM Input] Code Generation Task for file {task.parameters['file_path']}:\n{task_desc}")

            gen_task = Task(description=task_desc, agent=code_gen_agent)

            # 执行生成
            crew = Crew(agents=[code_gen_agent], tasks=[gen_task])

            code_content = crew.kickoff()

            # 记录LLM输出
            self.log.info(
                f"[LLM Output] Generated code for file {task.parameters['file_path']}:\n{
                    code_content.raw if hasattr(code_content, 'raw') else code_content
                }"
            )

            # 创建资源
            resource_task = BotTask(
                type=TaskType.RESOURCE_CREATION,
                priority=task.priority,
                description=f"保存生成的代码: {task.parameters['file_path']}",
                parameters={
                    "file_path": task.parameters["file_path"],
                    "mime_type": task.parameters["mime_type"],
                    "code_content": code_content,
                    "opera_id": task.parameters["opera_id"],
                },
            )

            # 使用资源处理器保存代码
            await self.resource_handler.handle_resource_creation(resource_task)

            # 更新任务状态
            task.result = {"file_path": task.parameters["file_path"], "resource_task_result": resource_task.result}
            await self.task_queue.update_task_status(task.id, TaskStatus.COMPLETED)

        except Exception as e:
            self.log.error(f"代码生成失败: {str(e)}")
            await self.task_queue.update_task_status(task.id, TaskStatus.FAILED)
            task.error_message = str(e)

    async def _process_task(self, task: BotTask):
        """处理任务，包括主题任务跟踪"""
        # 1. 处理需要转发的任务
        if task.response_staff_id in self.crew_processes:
            cr_process = self.crew_processes[task.response_staff_id]
            await self._update_cr_task_queue(cr_process.bot_id, task)
            return

        # 2. 处理资源创建任务
        if task.type == TaskType.RESOURCE_CREATION:
            if task.topic_id:
                self.topic_tracker.add_task(task)
            await self.resource_handler.handle_resource_creation(task)
            return

        # 3. 其他任务交给父类处理
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
                    default_tags=json.dumps({"TaskStates": [PersistentTaskState.from_bot_task(task).model_dump(by_alias=True)]}),
                    is_default_roles_updated=False,
                    default_roles=None,
                    is_default_permissions_updated=False,
                    default_permissions=None,
                ),
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
            await self.task_queue.update_task_status(task_id=UUID(task_id), new_status=TaskStatus.COMPLETED)

            # 更新当前回调任务的状态
            await self.task_queue.update_task_status(task_id=task.id, new_status=TaskStatus.COMPLETED)

            # 记录日志
            self.log.info(f"任务 {task_id} 已完成，结果: {result}")

        except Exception as e:
            self.log.error(f"处理任务回调时发生错误: {str(e)}")
            raise

    async def _handle_topic_completed(self, topic_id: str, topic_type: str, opera_id: str):
        """处理主题完成回调

        当一个主题的所有任务都完成时，发送一个包含所有资源信息的对话。

        Args:
            topic_id: 主题ID
            topic_type: 主题类型
            opera_id: Opera ID
        """
        try:
            # 获取CM的staff_id
            cm_staff_id = await self._get_cm_staff_id(opera_id)
            if not cm_staff_id:
                self.log.error(f"无法为主题 {topic_id} 创建总结任务：无法获取CM的staff_id")
                return

            # 获取该主题的所有已完成任务
            completed_tasks = [
                task
                for task in self.task_queue.tasks
                if task.topic_id == topic_id and task.status == TaskStatus.COMPLETED and task.type == TaskType.RESOURCE_CREATION
            ]

            # 使用字典保留每个文件路径的最新任务
            latest_tasks = {}
            for task in completed_tasks:
                file_path = task.parameters.get("file_path")
                if not file_path:
                    continue

                # 比较创建时间，保留最新版本
                existing_task = latest_tasks.get(file_path)
                if not existing_task or task.completed_at > existing_task.completed_at:
                    latest_tasks[file_path] = task

            # 构建资源列表
            resources = []
            for task in latest_tasks.values():
                if task.result and isinstance(task.result, dict):
                    resource_info = {
                        "Url": task.parameters.get("file_path", ""),
                        "ResourceId": task.result.get("resource_id", ""),
                        "ResourceCacheable": True,
                    }
                    resources.append(resource_info)

            # 构建ResourcesForViewing标签
            resources_tag = {"ResourcesForViewing": {"VersionId": topic_id, "Resources": resources, "NavigateIndex": 0}, "RemovingAllResources": True}

            # 创建对话消息
            dialogue_data = DialogueForCreation(
                is_stage_index_null=False,
                staff_id=str(cm_staff_id),
                is_narratage=False,
                is_whisper=False,
                text=f"主题 {topic_id} 的所有资源已生成完成。",
                tags=json.dumps(resources_tag),
            )

            # 发送对话
            result = _SHARED_DIALOGUE_TOOL.run(action="create", opera_id=opera_id, data=dialogue_data)

            # 检查结果
            status_code, _ = ApiResponseParser.parse_response(result)
            if status_code not in [200, 201, 204]:
                self.log.error(f"发送主题 {topic_id} 完成对话失败")
                return

            self.log.info(f"已发送主题 {topic_id} 完成对话，包含 {len(resources)} 个资源")

        except Exception as e:
            self.log.error(f"处理主题完成回调时发生错误: {str(e)}")


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

        for agent_config in self.config.get("agents", []):
            agent = Agent(
                name=agent_config["name"],
                role=agent_config["role"],
                goal=agent_config["goal"],
                backstory=agent_config["backstory"],
                tools=agent_config.get("tools", []),
            )
            agents.append(agent)

            if "task" in agent_config:
                task = Task(description=agent_config["task"], agent=agent)
                tasks.append(task)

        return Crew(agents=agents, tasks=tasks, process=self.config.get("process", "sequential"), verbose=True)

    async def _handle_generation_task(self, task: BotTask):
        """处理代码生成类型的任务"""
        try:
            # 使用已配置的agents
            if not self.crew or not self.crew.agents:
                raise Exception("Crew或agents未正确配置")

            # 创建代码生成任务
            task_desc = f"""根据以下信息生成代码：
                1. 文件路径：{task.parameters["file_path"]}
                2. 文件类型：{task.parameters["file_type"]}
                3. 需求描述：{task.parameters["dialogue_context"]["text"]}
                4. 项目信息：
                   - 类型：{task.parameters["code_details"]["project_type"]}
                   - 描述：{task.parameters["code_details"]["project_description"]}
                   - 框架：{task.parameters["code_details"]["frameworks"]}
                5. 相关文件：{task.parameters["code_details"]["resources"]}
                6. 引用关系：{task.parameters.get("references", [])}
                """

            # 记录LLM输入
            self.log.info(f"[LLM Input] Generation Task for file {task.parameters['file_path']}:\n{task_desc}")

            gen_task = Task(
                description=task_desc,
                agent=self.crew.agents[0],  # 使用已配置的agent
                expected_output=f"""
                @file: {task.parameters["file_path"]}
                @description: [简要描述文件的主要功能和用途]
                @tags: [相关标签，如framework_xxx,feature_xxx等，用逗号分隔]
                @version: 1.0.0
                @version_id: [UUID格式的版本ID]
                ---
                [完整的代码实现，包含：
                1. 必要的导入语句
                2. 类型定义（如果需要）
                3. 主要功能实现
                4. 错误处理
                5. 导出语句（如果需要）]""",
            )

            # 执行生成
            self.crew.tasks = [gen_task]
            result = self.crew.kickoff()
            code_content = result.raw if hasattr(result, "raw") else str(result)

            # 记录LLM输出
            self.log.info(f"[LLM Output] Generated code for file {task.parameters['file_path']}:\n{code_content}")

            # 通过dialogue发送代码生成结果
            dialogue_data = DialogueForCreation(
                is_stage_index_null=False,
                staff_id=str(task.response_staff_id),
                is_narratage=False,
                is_whisper=False,
                text=code_content,
                tags=f"CODE_RESOURCE;SKIP_ANALYSIS;TOPIC_ID:{task.topic_id}" if task.topic_id else "CODE_RESOURCE;SKIP_ANALYSIS",
                # mentioned_staff_ids=[str(task.source_staff_id)]
            )

            # 使用dialogue_api_tool发送对话
            result = _SHARED_DIALOGUE_TOOL.run(action="create", opera_id=task.parameters["opera_id"], data=dialogue_data)

            # 检查结果
            status_code, response_data = ApiResponseParser.parse_response(result)
            if status_code not in [200, 201, 204]:
                raise Exception(f"发送代码生成对话失败: {result}")

            # 更新任务状态和结果
            task.status = TaskStatus.COMPLETED
            task.result = {
                "dialogue_id": response_data["index"],
                "status": "success",
                # "text": response_data["text"]
            }

            # 发送任务完成回调
            await self._handle_task_completion(task, json.dumps(task.result))

        except Exception as e:
            self.log.error(f"代码生成任务处理失败: {str(e)}")
            task.error_message = str(e)
            task.status = TaskStatus.FAILED
            # 发送错误回调
            error_result = {"status": "failed", "error": str(e)}
            await self._handle_task_completion(task, json.dumps(error_result))

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
                        "parameters": {"callback_task_id": str(task.id), "result": json.loads(result), "opera_id": task.parameters.get("opera_id")},
                    }),
                    tags="task_callback",
                    mentioned_staff_ids=[str(task.source_staff_id)],
                ),
            )

            # 检查回调消息是否创建成功
            status_code, _ = ApiResponseParser.parse_response(callback_result)
            if status_code not in [200, 204, 201]:
                self.log.error(f"创建任务回调消息失败: {callback_result}")

        except Exception as e:
            self.log.error(f"发送任务回调时发生错误: {str(e)}")
