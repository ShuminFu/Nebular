from typing import Dict, List, Optional
from uuid import UUID
from dataclasses import dataclass
import asyncio
import multiprocessing
from abc import ABC, abstractmethod
from crewai import Crew
from src.opera_service.api.models import BotForUpdate, DialogueForCreation
from src.core.logger_config import get_logger_with_trace_id
from src.core.parser.api_response_parser import ApiResponseParser
from src.opera_service.signalr_client.opera_signalr_client import OperaSignalRClient, MessageReceivedArgs
from src.crewai_ext.tools.opera_api.bot_api_tool import _SHARED_BOT_TOOL
from src.crewai_ext.tools.opera_api.dialogue_api_tool import _SHARED_DIALOGUE_TOOL
from src.core.intent_mind import IntentMind
from src.core.task_utils import BotTaskQueue, TaskType, TaskStatus, BotTask, PersistentTaskState, TaskPriority
from src.core.code_monkey import CodeMonkey
from src.core.topic.topic_tracker import TopicTracker
from src.crewai_ext.crew_bases.runner_crewbase import RunnerCodeGenerationCrew, GenerationInputs, RunnerChatCrew
from src.crewai_ext.crew_bases.manager_crewbase import ManagerCrew, ManagerChatCrew
from src.crewai_ext.crew_bases.resource_iteration_crewbase import IterationAnalyzerCrew
import json
import litellm


@dataclass
class CrewProcessInfo:
    """工作型Crew进程信息"""

    process: multiprocessing.Process
    bot_id: UUID
    crew_config: dict  # 新增CR配置字段, 设计上这个CR的所有staff都将使用这个配置
    opera_ids: List[UUID]
    roles: Dict[UUID, List[str]]  # opera id 为键，staff roles为值
    staff_ids: Dict[UUID, List[UUID]]  # opera id 为键，staff id 为值


class BaseCrewProcess(ABC):
    """Crew进程的基类，定义共同的接口和功能"""

    def __init__(self):
        self.bot_id: Optional[UUID] = None
        self.client: Optional[OperaSignalRClient] = None
        self.is_running: bool = True
        self.crew: Optional[Crew] = None
        # 为每个进程创建一个带trace_id的logger
        self.log = get_logger_with_trace_id()
        self._staff_id_cache: Dict[str, Dict[UUID, UUID]] = {}  # opera_id -> {bot_id -> staff_id} 的缓存
        self.crew = self._setup_crew()

    async def setup(self):
        """初始化设置"""
        self.task_queue = BotTaskQueue(bot_id=self.bot_id)
        self.intent_processor = IntentMind(self.task_queue, self._get_crew_processes())

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
                # 并行处理连接检查和任务处理
                await asyncio.gather(
                    self._check_connection(),
                    self._process_pending_tasks(),
                )
        except Exception as e:
            self.log.exception(f"Crew运行出错: {e}")
        finally:
            await self.stop()

    async def _check_connection(self):
        """非阻塞的连接状态检查"""
        if self.client and not self.client.is_connected():
            self.log.warning("连接断开，尝试重连...")
            await self.setup()
        await asyncio.sleep(1)  # 控制检查频率

    async def _process_pending_tasks(self):
        """处理待办任务"""
        while task := await self.task_queue.get_next_task():
            asyncio.create_task(  
                self._process_task(task)
            )

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
            await self.task_queue.update_task_status(task.id, TaskStatus.FAILED)

    async def _handle_message(self, message: MessageReceivedArgs):
        """处理接收到的消息"""
        self.log.info(f"收到消息: {message.text}")
        try:
            # 获取消息的opera_id
            opera_id = message.opera_id
            if not opera_id:
                self.log.error("消息缺少opera_id")
                return

            # 获取当前Bot的staff_id
            current_staff_id = await self._get_bot_staff_id(self.bot_id, opera_id)
            if not current_staff_id:
                self.log.error("无法获取当前Bot的staff_id")
                return

            # 检查是否是自己的消息
            if str(message.sender_staff_id) == str(current_staff_id):
                self.log.info("忽略自己发送的消息，避免循环")
                return

            asyncio.create_task(self.intent_processor.process_message(message))
        except Exception as e:
            self.log.error(f"处理消息时发生错误: {str(e)}")

    @abstractmethod
    def _setup_crew(self) -> Crew:
        """设置Crew配置，由子类实现"""
        pass
    @abstractmethod
    def _get_crew_processes(self) -> Optional[Dict[UUID, CrewProcessInfo]]:
        """获取当前进程的配置，由子类实现"""
        pass
    
    async def _handle_conversation_task(self, task: BotTask):
        """处理对话类型的任务"""
        try:
            # 获取对话内容和参数
            input_text = task.parameters.get("text", "")

            if not input_text:
                self.log.error("对话任务缺少dialogue_context参数")
                return

            context = task.parameters.get("context", {})  # 直接获取context参数

            # 组合完整的对话上下文
            full_context = json.dumps(
                {
                    "text": input_text,
                    "stage_index": context.get("stage_index"),
                    "conversation_state": context.get("conversation_state", {}),
                },
                ensure_ascii=False,
            )
            self.log.info(f"对话任务输入: {full_context}")
            # 使用Crew生成回复
            try:
                result = await self.chat_crew.crew().kickoff_async(inputs={"text": full_context})
                self.log.info(f"对话任务结果: {result.raw}")
                
                # 获取回复文本
                reply_text = result.raw if hasattr(result, "raw") else str(result)
                if reply_text.startswith("```json\n"):
                    reply_text = reply_text[8:]
                if reply_text.endswith("\n```"):
                    reply_text = reply_text[:-4]

                reply_json = json.loads(reply_text)
                reply_text = reply_json.get("reply_text", "").strip()
                
            except json.JSONDecodeError as e:
                error_msg = f"LLM响应解析失败: {str(e)}"
                self.log.error(error_msg)
                reply_text = "抱歉，我的回复似乎出现了格式问题，请检查我的输出内容"
            except litellm.APIConnectionError as e:
                error_msg = f"LLM服务连接失败: {str(e)}"
                self.log.error(error_msg)
                reply_text = "当前AI服务连接不稳定，请稍后再试"
                
                # 直接发送错误通知
                dialogue_data = DialogueForCreation(
                    is_stage_index_null=False,
                    staff_id=str(task.response_staff_id),
                    is_narratage=False,
                    is_whisper=False,  
                    text=f"⚠️ 系统通知：{error_msg}",
                    tags="LLM_ERROR;SYSTEM_ALERT",
                )
                _SHARED_DIALOGUE_TOOL.run(
                    action="create",
                    opera_id=task.parameters.get("opera_id"),
                    data=dialogue_data,
                )
            except Exception as e:
                error_msg = f"对话处理异常: {str(e)}"
                self.log.error(error_msg)
                reply_text = "处理您的请求时遇到意外错误，请联系管理员"
            
            # 构造对话消息
            dialogue_data = DialogueForCreation(
                is_stage_index_null=False,
                staff_id=str(task.response_staff_id),
                is_narratage=False,
                is_whisper=False,
                text=reply_text,
            )

            # 发送对话
            result = _SHARED_DIALOGUE_TOOL.run(
                action="create",
                opera_id=task.parameters.get("opera_id"),
                data=dialogue_data,
            )

            # 检查结果
            status_code, _ = ApiResponseParser.parse_response(result)
            if status_code not in [200, 201, 204]:
                raise Exception(f"发送对话失败: {result}")

            # 更新任务状态
            await self.task_queue.update_task_status(task.id, TaskStatus.COMPLETED)
            task.result = {
                "status": "success",
                "reply": reply_text
            }

        except Exception as e:
            self.log.error(f"处理对话任务失败: {str(e)}")
            task.error_message = str(e)

    @abstractmethod
    async def _handle_generation_task(self, task: BotTask):
        """处理生成类型的任务"""
        pass

    async def _handle_task_callback(self, task: BotTask):
        """处理任务回调"""
        pass

    async def _get_bot_staff_id(self, bot_id: UUID, opera_id: str) -> Optional[UUID]:
        """获取指定Bot在特定Opera中的staff_id

        Args:
            bot_id: Bot的ID
            opera_id: Opera的ID

        Returns:
            Optional[UUID]: 如果找到则返回staff_id，否则返回None
        """
        # 先检查缓存
        cache_key = str(opera_id)
        if cache_key in self._staff_id_cache and bot_id in self._staff_id_cache[cache_key]:
            return self._staff_id_cache[cache_key][bot_id]

        try:
            # 使用bot_api_tool获取Bot的所有Staff信息
            result = _SHARED_BOT_TOOL.run(
                action="get_all_staffs",
                bot_id=bot_id,
                data={"need_opera_info": True, "need_staffs": 1, "need_staff_invitations": 0},
            )

            # 解析API响应
            status_code, data = ApiResponseParser.parse_response(result)
            if status_code != 200 or not data:
                self.log.error(f"获取Bot {bot_id} 的Staff信息失败")
                return None

            # 遍历所有Opera的Staff信息
            for opera_info in data:
                if str(opera_info.get("operaId")) == str(opera_id):
                    staffs = opera_info.get("staffs", [])
                    if staffs:
                        # 找到第一个属于这个Bot的Staff
                        staff_id = UUID(staffs[0].get("id"))
                        # 初始化缓存字典
                        if cache_key not in self._staff_id_cache:
                            self._staff_id_cache[cache_key] = {}
                        # 缓存结果
                        self._staff_id_cache[cache_key][bot_id] = staff_id
                        return staff_id

            self.log.error(f"在Opera {opera_id} 中未找到Bot {bot_id} 的Staff")
            return None

        except Exception as e:
            self.log.error(f"获取Bot的staff_id时发生错误: {str(e)}")
            return None


class CrewManager(BaseCrewProcess):
    """管理所有工作型Crew的进程"""

    def __init__(self):
        super().__init__()
        self.crew_processes: Dict[UUID, CrewProcessInfo] = {}

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

    def _setup_crew(self) -> Crew:
        self.chat_crew = ManagerChatCrew()
        return ManagerCrew()

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
        return await self._get_bot_staff_id(self.bot_id, opera_id)
    
    def _get_crew_processes(self) -> Optional[Dict[UUID, CrewProcessInfo]]:
        """获取所有子Crew的配置集合"""
        return self.crew_processes

    async def _handle_conversation_task(self, task: BotTask):
        """处理对话类型的任务"""
        # 实现CrewManager特定的对话任务处理逻辑
        await super()._handle_conversation_task(task)

    async def _handle_generation_task(self, task: BotTask):
        """处理动作类型的任务"""
        # 实现CrewManager特定的动作任务处理逻辑
        pass

    async def _handle_analysis_task(self, task: BotTask):
        """处理分析类型的任务"""
        # 实现CrewManager特定的分析任务处理逻辑
        pass


    async def _process_task(self, task: BotTask):
        """处理任务，包括主题任务跟踪"""
        # 1. 处理需要转发的任务
        cr_for_task = None
        for cr_bot_id, cr_info in self.crew_processes.items():
            # 遍历每个CR的所有opera中的staff_ids
            for opera_id, staff_ids in cr_info.staff_ids.items():
                if task.response_staff_id in staff_ids:
                    cr_for_task = cr_info
                    break
            if cr_for_task:
                break

        # 找到CR后转发任务
        if cr_for_task:
            await self._update_cr_task_queue(cr_for_task.bot_id, task)
            return

        # 2. 处理资源创建任务
        if task.type == TaskType.RESOURCE_CREATION:
            if task.topic_id:
                self.topic_tracker.add_task(task)
            await self.resource_handler.handle_resource_creation(task)
            return
        if task.type == TaskType.RESOURCE_ITERATION:
            # 解析Tags中的资源信息
            tags = json.loads(task.parameters.get("tags", "{}"))
            resource_list = []
            version_id = None
            
            # 场景1：直接包含资源列表
            for tag_key in ["ResourcesForViewing", "ResourcesForIncarnating", "ResourcesMentionedFromViewer"]:
                if tag_key in tags:
                    resources = tags[tag_key].get("Resources", [])
                    resource_list.extend([
                        {
                            "file_path": res["Url"],
                            "resource_id": res["ResourceId"]
                        } for res in resources
                    ])
            
            # 场景2：通过SelectedTextsFromViewer获取version_id
            if not resource_list and "SelectedTextsFromViewer" in tags:
                selected_items = tags["SelectedTextsFromViewer"]
                if selected_items:
                    version_id = selected_items[0].get("VersionId")
            
            # 场景3：从TopicTracker获取资源列表
            if version_id and not resource_list:
                try:
                    # 从主题追踪器获取版本对应资源
                    topic_info = self.topic_tracker.get_topic_info(version_id)
                    if topic_info:
                        resource_list = [
                            {
                                "file_path": res["file_path"],
                                "resource_id": res["resource_id"]
                            } for res in topic_info.current_version.current_files
                        ]
                except Exception as e:
                    self.log.error(f"获取版本资源失败: {str(e)}")
                    await self.task_queue.update_task_status(task.id, TaskStatus.FAILED)
                    return
            
            # 去重处理
            seen = set()
            unique_resources = [
                r for r in resource_list 
                if not (r["resource_id"] in seen or seen.add(r["resource_id"]))
            ]
            
            # 调用Crew进行任务分解
            analysis_result = await IterationAnalyzerCrew().crew().kickoff_async(
                inputs={
                    "iteration_requirement": task.parameters["text"],
                    "resource_list": unique_resources
                }
            )
            
            # TODO select CR然后分发子任务
            pass

        if task.type == TaskType.CHAT_PLANNING:
            pass

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

            # 首先获取CR的当前信息
            get_result = _SHARED_BOT_TOOL.run(
                action="get",
                bot_id=cr_bot_id,
                data=None,
            )

            # 检查获取结果
            status_code, bot_data = ApiResponseParser.parse_response(get_result)
            if status_code != 200 or not bot_data:
                self.log.error(f"获取CrewRunner {cr_bot_id} 的信息失败")
                return

            # 解析现有的default_tags
            current_default_tags = {}
            if bot_data.get("defaultTags"):
                try:
                    current_default_tags = json.loads(bot_data["defaultTags"])
                except json.JSONDecodeError:
                    self.log.warning(f"解析CrewRunner {cr_bot_id} 的default_tags失败，将创建新的default_tags")

            # 更新TaskStates字段
            task_state = PersistentTaskState.from_bot_task(task).model_dump(by_alias=True)
            if "TaskStates" not in current_default_tags:
                current_default_tags["TaskStates"] = [task_state]
            else:
                # 添加新任务状态
                current_default_tags["TaskStates"].append(task_state)

            # 获取CR在当前opera中的staff_id
            cr_staff_id = None
            for opera_id_str, staff_ids in self.crew_processes[cr_bot_id].staff_ids.items():
                if str(opera_id_str) == str(opera_id) and staff_ids:
                    cr_staff_id = staff_ids[0]  # 获取第一个staff_id
                    break

            if not cr_staff_id:
                self.log.error(f"无法获取CrewRunner {cr_bot_id} 在Opera {opera_id} 中的staff_id")
                return

            # 构建任务描述消息
            task_description = f"请根据描述完成代码生成任务: {task_state}"

            # 创建对话消息
            dialogue_data = DialogueForCreation(
                is_stage_index_null=False,
                staff_id=str(cm_staff_id),
                is_narratage=False,
                is_whisper=True,  # 设置为私聊
                text=task_description,
                tags=f"TASK_ASSIGNMENT;TASK_ID:{task.id}",
                mentioned_staff_ids=[str(cr_staff_id)],  # 提及CR的staff
            )

            # 并发执行更新defaultTags和发送对话两个操作
            async def update_default_tags():
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
                        default_tags=json.dumps(current_default_tags),
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
                    return False
                return True

            async def send_dialogue():
                # 发送对话
                dialogue_result = _SHARED_DIALOGUE_TOOL.run(
                    action="create",
                    opera_id=opera_id,
                    data=dialogue_data,
                )
                # 检查对话发送结果
                status_code, _ = ApiResponseParser.parse_response(dialogue_result)
                if status_code not in [200, 201, 204]:
                    self.log.error(f"发送任务分配对话失败: {dialogue_result}")
                    return False
                return True

            # 并发执行两个操作
            update_success, dialogue_success = await asyncio.gather(update_default_tags(), send_dialogue())

            # 检查两个操作是否都成功
            if update_success and dialogue_success:
                self.log.info(f"已成功将任务 {task.id} 分配给CrewRunner {cr_bot_id}")
            else:
                self.log.warning(f"任务 {task.id} 分配给CrewRunner {cr_bot_id} 部分失败")

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
            html_files = []  # 存储所有HTML文件路径
            for task in latest_tasks.values():
                if task.result and isinstance(task.result, dict):
                    file_path = task.parameters.get("file_path", "")
                    resource_info = {
                        "Url": file_path,
                        "ResourceId": task.result.get("resource_id", ""),
                        "ResourceCacheable": True,
                    }
                    resources.append(resource_info)

                    # 收集HTML文件路径用于导航判断
                    if file_path.lower().endswith(".html"):
                        html_files.append(file_path)

            topic_info = self.topic_tracker.get_topic_info(topic_id)
            current_version = topic_info.current_version
            if len(current_version.current_files) != len(current_version.modified_files):
                # TODO: Removing, adding or updating flag here. Hashing the files to check if there are any changes.
                pass

            # 构建ResourcesForViewing标签的基本结构
            resources_tag = {
                "ResourcesForViewing": {
                    "VersionId": topic_id,
                    "Resources": resources,
                    "CurrentVersion": current_version,
                },
                "RemovingAllResources": True,
            }

            # 只有在找到index.html时才添加NavigateIndex字段
            if html_files:
                # 查找index.html（精确匹配）
                index_html = next((i for i, p in enumerate(html_files) if p.lower().endswith("/index.html") or p == "index.html"), None)
                if index_html is not None:
                    # 找到index.html，添加NavigateIndex字段
                    resources_tag["ResourcesForViewing"]["NavigateIndex"] = html_files.index(html_files[index_html])

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

    def __init__(self, bot_id: UUID, parent_bot_id: Optional[UUID] = None, crew_config: Optional[dict] = None):
        self.crew_config = crew_config  # 存储动态配置
        super().__init__()
        self.bot_id = bot_id
        self.parent_bot_id = parent_bot_id

        self.chat_crew = RunnerChatCrew()

    async def _get_parent_staff_id(self, opera_id: str) -> Optional[UUID]:
        """获取父Bot在指定Opera中的staff_id

        Args:
            opera_id: Opera的ID

        Returns:
            Optional[UUID]: 如果找到则返回staff_id，否则返回None
        """
        if not self.parent_bot_id:
            return None
        return await self._get_bot_staff_id(self.parent_bot_id, opera_id)

    def _setup_crew(self) -> Crew:
        """根据配置动态创建Crew"""
        if self.crew_config:
            DynamicCrewClass = RunnerCodeGenerationCrew.create_dynamic_crew(self.crew_config)
            return DynamicCrewClass()
        return RunnerCodeGenerationCrew()

    def _get_crew_processes(self) -> Optional[Dict[UUID, CrewProcessInfo]]:
        return None

    async def _handle_generation_task(self, task: BotTask):
        """处理代码生成类型的任务"""
        try:
            # 准备代码生成输入参数
            generation_inputs = GenerationInputs(
                file_path=task.parameters["file_path"],
                file_type=task.parameters["file_type"],
                requirement=task.parameters["dialogue_context"]["text"],
                project_type=task.parameters["code_details"]["project_type"],
                project_description=task.parameters["code_details"]["project_description"],
                frameworks=task.parameters["code_details"]["frameworks"],
                resources=task.parameters["code_details"]["resources"],
                references=task.parameters.get("references", []),
            )

            # 记录LLM输入
            self.log.info(
                f"[LLM Input] Generation Task for file {task.parameters['file_path']}:\n{generation_inputs.model_dump_json()}"
            )

            result = await self.crew.crew().kickoff_async(inputs=generation_inputs.model_dump())
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
            await self.task_queue.update_task_status(task.id, TaskStatus.COMPLETED)
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

    async def _handle_analysis_task(self, task: BotTask):
        """处理分析类型的任务"""
        # 实现CrewRunner特定的分析任务处理逻辑
        pass

    async def _handle_conversation_task(self, task: BotTask):
        """处理对话类型的任务"""
        # 实现CrewRunner特定的对话任务处理逻辑
        await super()._handle_conversation_task(task)

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

    async def _handle_message(self, message: MessageReceivedArgs):
        """处理接收到的消息

        只处理以下情况的消息：
        1. 发送者是父Bot的staff
        2. 消息是非提及对话或者提及了当前Bot
        """
        try:
            # 获取消息的opera_id
            opera_id = message.opera_id
            if not opera_id:
                self.log.error("消息缺少opera_id")
                return

            # 获取父Bot的staff_id
            parent_staff_id = await self._get_parent_staff_id(opera_id)
            if not parent_staff_id:
                self.log.debug(f"无法获取父Bot在Opera {opera_id} 中的staff_id，跳过消息处理")
                return

            # 检查发送者是否是父Bot的staff
            if str(message.sender_staff_id) != str(parent_staff_id):
                self.log.debug(f"消息发送者 {message.sender_staff_id} 不是父Bot的staff {parent_staff_id}，跳过消息处理")
                return
            elif not message.tags:
                self.log.debug("消息没有包含任何tag，已忽略...")
                return

            # 获取当前Bot的staff_id
            current_bot_staff_id = await self._get_bot_staff_id(self.bot_id, opera_id)
            if not current_bot_staff_id:
                self.log.error(f"无法获取当前Bot在Opera {opera_id} 中的staff_id")
                return

            # 检查消息是否是私聊(whisper)
            if message.is_whisper:
                # 如果是私聊且当前Bot在receiver_staff_ids中
                receiver_ids = [str(id) for id in (message.receiver_staff_ids or [])]
                if str(current_bot_staff_id) in receiver_ids:
                    self.log.info("收到父Bot发送的私聊消息，处理中...")
                    await super()._handle_message(message)
                    return

            # 检查消息是否提及了当前Bot
            mentioned_staff_ids = [str(id) for id in (message.mentioned_staff_ids or [])]
            if str(current_bot_staff_id) in mentioned_staff_ids:
                self.log.info("收到提及当前Bot的消息，处理中...")
                await super()._handle_message(message)
                return

            # 检查是否是非提及对话(公开消息)
            if not message.mentioned_staff_ids:
                self.log.info("收到非提及的公开消息，已忽略...")
                return

            self.log.debug("消息不满足处理条件，跳过处理")
        except Exception as e:
            self.log.error(f"处理消息时发生错误: {str(e)}")
