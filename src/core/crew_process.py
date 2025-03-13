from typing import Dict, List, Optional
from uuid import UUID
from dataclasses import dataclass
import asyncio
import multiprocessing
import json
from abc import ABC, abstractmethod
from crewai import Crew
from src.opera_service.api.models import DialogueForCreation
from src.core.logger_config import get_logger_with_trace_id
from src.core.parser.api_response_parser import ApiResponseParser
from src.opera_service.signalr_client.opera_signalr_client import OperaSignalRClient, MessageReceivedArgs, OperaCreatedArgs
from src.crewai_ext.tools.opera_api.bot_api_tool import _SHARED_BOT_TOOL
from src.crewai_ext.tools.opera_api.dialogue_api_tool import _SHARED_DIALOGUE_TOOL
from src.core.intent_mind import IntentMind
from src.core.task_utils import BotTaskQueue, TaskType, TaskStatus, BotTask

import litellm
import time

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
            self.client.set_callback("on_opera_created", self._handle_opera_created)
            self.client.set_callback("on_opera_deleted", self._handle_opera_deleted)

    async def stop(self):
        """停止Crew运行"""
        self.is_running = False
        if self.client:
            await self.client.disconnect()

    async def run(self):
        """运行Crew的主循环"""
        try:
            await self.setup()
            time.sleep(3)
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
        self.log.info(f"收到消息: {message.index}")
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

            self.log.info(f"正在处理消息: {message.text}")

            asyncio.create_task(self.intent_processor.process_message(message))
        except Exception as e:
            self.log.error(f"处理消息时发生错误: {str(e)}")

    async def _handle_opera_created(self, opera_args: OperaCreatedArgs):
        """处理Opera创建事件"""
        # 这里可以添加对Opera创建事件的逻辑处理
        pass

    async def _handle_opera_deleted(self, opera_args: OperaCreatedArgs):
        """处理Opera删除事件"""
        # 这里可以添加对Opera删除事件的逻辑处理
        pass

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
