from typing import Dict, Optional
from uuid import UUID
import json
from crewai import Crew
from src.opera_service.api.models import DialogueForCreation
from src.core.parser.api_response_parser import ApiResponseParser
from src.opera_service.signalr_client.opera_signalr_client import MessageReceivedArgs
from src.crewai_ext.tools.opera_api.dialogue_api_tool import _SHARED_DIALOGUE_TOOL
from src.core.task_utils import TaskType, TaskStatus, BotTask, TaskPriority

from src.crewai_ext.crew_bases.runner_crewbase import RunnerCodeGenerationCrew, GenerationInputs, RunnerChatCrew

from src.crewai_ext.tools.opera_api.resource_api_tool import ResourceTool
from src.core.crew_process import BaseCrewProcess, CrewProcessInfo


class CrewRunner(BaseCrewProcess):
    """在独立进程中运行的Crew"""

    def __init__(self, bot_id: UUID, parent_bot_id: Optional[UUID] = None, crew_config: Optional[dict] = None):
        self.crew_config = crew_config  # 存储动态配置
        super().__init__()
        self.bot_id = bot_id
        self.parent_bot_id = parent_bot_id
        self.roles = ["CrewRunner"]  # 设置角色

        self.chat_crew = RunnerChatCrew()

    async def setup(self):
        """初始化设置"""
        await super().setup()
        self.client.set_callback("on_staff_invited", self._handle_staff_invited)

    async def _handle_staff_invited(self, invite_data: dict):
        """处理Staff邀请事件

        Args:
            invite_data: 邀请数据，包含opera_id, invitation_id等
        """
        self.log.info(f"收到Staff邀请事件: {invite_data}")
        try:
            # 验证必要的参数
            required_fields = ["opera_id", "invitation_id", "roles", "permissions"]
            for field in required_fields:
                if field not in invite_data:
                    raise ValueError(f"缺少必要的字段: {field}")

            # 准备接受邀请所需的数据
            opera_id = invite_data["opera_id"]
            invitation_id = invite_data["invitation_id"]

            # 构造bot名称
            bot_name = f"{self.__class__.__name__}_Bot"
            if hasattr(self, "roles") and self.roles:  # 如果有设置角色，使用角色作为名称
                bot_name = f"Bot_{','.join(self.roles)}"

            # 构造接受邀请的数据
            from src.opera_service.api.models import StaffInvitationForAcceptance

            acceptance_data = StaffInvitationForAcceptance(
                name=bot_name,
                parameter=json.dumps(invite_data.get("parameter", {})),
                is_on_stage=True,
                tags=invite_data.get("tags", ""),
                roles=invite_data.get("roles", ""),
                permissions=invite_data.get("permissions", ""),
            )

            # 使用StaffInvitationTool接受邀请
            from src.crewai_ext.tools.opera_api.staff_invitation_api_tool import StaffInvitationTool

            staff_invitation_tool = StaffInvitationTool()
            result = staff_invitation_tool.run(
                action="accept", opera_id=opera_id, invitation_id=invitation_id, data=acceptance_data
            )
            self.log.info(f"自动接受邀请结果: {result}")

        except ValueError as e:
            self.log.error(f"参数验证失败: {str(e)}")
        except Exception as e:
            self.log.error(f"自动接受邀请失败: {str(e)}")
            self.log.exception("详细错误信息:")

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
            # 处理引用资源
            processed_references = []
            # 检查任务参数中是否包含opera_id和resource_id
            if task.parameters.get("opera_id") and task.parameters.get("resource_id"):
                # 初始化资源API工具
                resource_tool = ResourceTool()
                opera_id = task.parameters.get("opera_id")
                resource_id = task.parameters.get("resource_id")

                try:
                    # 调用资源API下载资源
                    ref_content = resource_tool._run(action="download", opera_id=opera_id, resource_id=resource_id)

                    # 处理二进制内容
                    if isinstance(ref_content, bytes):
                        # 尝试将二进制内容解码为文本
                        try:
                            ref_text = ref_content.decode("utf-8")
                            processed_references.append(ref_text)
                        except UnicodeDecodeError:
                            # 如果无法解码为文本，添加一条说明
                            processed_references.append(f"Binary content (size: {len(ref_content)} bytes) - {ref_content}")
                    else:
                        # 已经是字符串或其他格式
                        processed_references.append(str(ref_content))
                except Exception as e:
                    # 记录下载资源时的错误，但继续处理
                    self.log.error(f"下载引用资源时出错: {str(e)}")
                    processed_references.append(f"Error downloading reference: {str(e)}")
            else:
                # 如果没有opera_id或resource_id，直接使用原始引用
                processed_references = task.parameters.get("references", [])

            # 检查任务参数中是否包含action字段
            if "action" in task.parameters:
                # 使用另一套输入信息进行代码生成任务
                generation_inputs = GenerationInputs(
                    file_path=task.parameters["file_path"],
                    file_type=task.parameters["file_type"],
                    requirement=task.parameters["action"]
                    + (f" at {task.parameters['position']}" if task.parameters.get("position") else "")
                    + (f" for resource id: {task.parameters['resource_id']}" if task.parameters.get("resource_id") else "")
                    + (f" for opera id : {task.parameters['opera_id']}" if task.parameters.get("opera_id") else ""),
                    project_type=task.parameters["code_details"]["project_type"],
                    project_description=task.parameters["description"],
                    frameworks=task.parameters["code_details"]["frameworks"],
                    resources=task.parameters["code_details"]["resources"],
                    references=processed_references,
                )
            else:
                # 保持原有的输入参数构建方式
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
                    staff_id=str(task.response_staff_id),
                    is_narratage=False,
                    is_whisper=True,
                    text=json.dumps({
                        "type": TaskType.CALLBACK.value,
                        "priority": TaskPriority.URGENT.value,
                        "description": f"Callback for task {task.id}",
                        "parameters": {
                            "callback_task_id": str(task.id),
                            "result": json.loads(result),
                            "opera_id": task.parameters.get("opera_id"),
                        },
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
        3. 特殊处理TASK_ASSIGNMENT标签的消息
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

            # 变量标记是否是私聊或提及消息
            is_whisper_to_me = False
            is_mentioned_me = False

            # 检查消息是否是私聊(whisper)
            if message.is_whisper:
                # 如果是私聊且当前Bot在receiver_staff_ids中
                receiver_ids = [str(id) for id in (message.receiver_staff_ids or [])]
                if str(current_bot_staff_id) in receiver_ids:
                    self.log.info("收到父Bot发送的私聊消息，处理中...")
                    is_whisper_to_me = True

            # 检查消息是否提及了当前Bot
            mentioned_staff_ids = [str(id) for id in (message.mentioned_staff_ids or [])]
            if str(current_bot_staff_id) in mentioned_staff_ids:
                self.log.info("收到提及当前Bot的消息，处理中...")
                is_mentioned_me = True

            # 如果是私聊给我的或提及我的消息，再检查是否需要特殊处理
            if is_whisper_to_me and is_mentioned_me:
                # 特殊处理：检查是否是任务分配消息
                if message.tags and "TASK_ASSIGNMENT" in message.tags:
                    self.log.info("收到任务分配消息，直接处理...")
                    await self._handle_task_assignment_message(message)
                    return
                # 正常处理私聊或提及消息
                await super()._handle_message(message)
                return

            # 检查是否是非提及对话(公开消息)
            if not message.mentioned_staff_ids:
                self.log.info("收到非提及的公开消息，已忽略...")
                return

            self.log.debug("消息不满足处理条件，跳过处理")
        except Exception as e:
            self.log.error(f"处理消息时发生错误: {str(e)}")

    async def _handle_task_assignment_message(self, message: MessageReceivedArgs):
        """处理任务分配消息，直接从消息中重构任务并加入任务队列

        Args:
            message: 包含TASK_ASSIGNMENT标签的消息
        """
        try:
            # 从消息文本中提取任务信息
            try:
                # 解析任务数据
                task_data = self._parse_task_str(message.text)

                # 提取任务ID
                task_id = None
                if message.tags:
                    # 从标签中提取task_id
                    for tag in message.tags.split(";"):
                        if tag.startswith("TASK_ID:"):
                            task_id = tag.replace("TASK_ID:", "").strip()
                            break

                # 确保有任务ID
                if not task_id and "Id" in task_data:
                    task_id = task_data["Id"]

                if not task_id:
                    self.log.error("无法从消息中获取任务ID")
                    return

                # 创建BotTask对象
                from uuid import UUID
                from src.core.task_utils import BotTask, TaskType, TaskPriority, TaskStatus

                # 使用任务信息创建BotTask - 状态始终设为PENDING
                task = BotTask(
                    id=UUID(task_id),
                    priority=task_data.get("Priority", TaskPriority.NORMAL),
                    type=task_data.get("Type", TaskType.RESOURCE_GENERATION),
                    status=TaskStatus.PENDING,  # 任务初始状态始终为PENDING
                    description=task_data.get("Description", ""),
                    parameters=task_data.get("Parameters", {}),
                    source_dialogue_index=task_data.get("SourceDialogueIndex"),
                    source_staff_id=str(message.sender_staff_id),  # 使用消息发送者的staff_id作为source_staff_id
                    response_staff_id=task_data.get("ResponseStaffId"),
                    topic_id=task_data.get("TopicId"),
                    topic_type=task_data.get("TopicType"),
                )

                # 直接添加到任务队列
                await self.task_queue.add_task(task)
                self.log.info(f"已成功将任务 {task_id} 直接添加到任务队列")

            except Exception as e:
                self.log.error(f"解析任务数据失败: {str(e)}")
                # 如果解析失败，让IntentMind尝试处理
                await super()._handle_message(message)

        except Exception as e:
            self.log.error(f"处理任务分配消息时发生错误: {str(e)}")

    def _parse_task_str(self, task_str: str) -> dict:
        """安全地解析任务字符串为任务字典，处理枚举类型

        Args:
            task_str: 包含任务信息的字符串

        Returns:
            dict: 解析后的任务数据字典
        """
        from src.core.task_utils import TaskType, TaskPriority, TaskStatus
        import re
        import ast

        try:
            # 替换枚举值为字符串形式，以便ast.literal_eval可以解析
            # 例如: <TaskPriority.HIGH: 3> -> "TaskPriority.HIGH"
            enum_pattern = r"<(TaskPriority|TaskType|TaskStatus)\.([A-Z_]+): \d+>"
            task_str_safe = re.sub(enum_pattern, r'"\1.\2"', task_str)

            # 使用ast.literal_eval安全地解析字符串为字典
            task_dict = ast.literal_eval(task_str_safe)

            # 将字符串形式的枚举值转换回实际枚举
            for key, value in task_dict.items():
                if isinstance(value, str):
                    if value.startswith("TaskPriority."):
                        enum_name = value.split(".")[1]
                        task_dict[key] = getattr(TaskPriority, enum_name)
                    elif value.startswith("TaskType."):
                        enum_name = value.split(".")[1]
                        task_dict[key] = getattr(TaskType, enum_name)
                    elif value.startswith("TaskStatus."):
                        enum_name = value.split(".")[1]
                        task_dict[key] = getattr(TaskStatus, enum_name)

            return task_dict
        except Exception as e:
            self.log.error(f"解析任务字符串失败: {str(e)}")
            # 如果解析失败，返回一个空字典
            return {}
