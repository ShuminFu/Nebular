from typing import Dict, Optional
from uuid import UUID
import json
from crewai import Crew
from src.opera_service.api.models import BotForUpdate, DialogueForCreation
from src.core.parser.api_response_parser import ApiResponseParser
from src.crewai_ext.tools.opera_api.bot_api_tool import _SHARED_BOT_TOOL
from src.crewai_ext.tools.opera_api.dialogue_api_tool import _SHARED_DIALOGUE_TOOL
from src.core.task_utils import TaskType, TaskStatus, BotTask, PersistentTaskState
from src.core.code_monkey import CodeMonkey
from src.core.topic.topic_tracker import TopicTracker, VersionMeta
from src.crewai_ext.crew_bases.manager_crewbase import ManagerCrew, ManagerChatCrew
from src.crewai_ext.crew_bases.resource_iteration_crewbase import IterationAnalyzerCrew

from src.core.crew_process import BaseCrewProcess, CrewProcessInfo


class CrewManager(BaseCrewProcess):
    """管理所有工作型Crew的进程"""

    def __init__(self):
        super().__init__()
        self.crew_processes: Dict[UUID, CrewProcessInfo] = {}
        self.roles = ["CrewManager"]  # 设置角色

        # 初始化主题追踪器
        self.topic_tracker = TopicTracker()
        # 注册主题完成回调
        self.topic_tracker.on_completion(self._handle_topic_completed)

    async def setup(self):
        """初始化设置"""
        await super().setup()
        self.client.set_callback("on_staff_invited", self._handle_staff_invited)
        # 创建资源处理器
        self.resource_handler = CodeMonkey(self.task_queue, self.log)
        # 设置任务状态变更回调
        self.task_queue.add_status_callback(self._handle_task_status_changed)

    def _setup_crew(self) -> Crew:
        self.chat_crew = ManagerChatCrew()
        return ManagerCrew()

    async def _handle_task_status_changed(self, task_id: UUID, new_status: TaskStatus):
        """处理任务状态变更"""
        # 查找完整的任务对象
        task = next((t for t in self.task_queue.tasks if t.id == task_id), None)
        # 更新主题追踪器
        await self.topic_tracker.update_task_status(task_id, new_status, task)

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
        if task.type == TaskType.RESOURCE_GENERATION:
            # 检查任务参数中是否包含action信息
            need_forward_to_cr = False

            # 检查任务参数中的code_details
            code_details = task.parameters.get("code_details", {})
            resources = code_details.get("resources", [])

            if resources:
                # 获取当前任务对应的文件路径
                target_file = task.parameters.get("file_path")

                # 在资源列表中查找匹配当前任务文件路径的资源
                target_resource = next((res for res in resources if res.get("file_path") == target_file), None)

                # 只检查目标资源的action
                if target_resource:
                    action = target_resource.get("action", "").lower()
                    if not action or action in ["create", "update"]:
                        need_forward_to_cr = True

            # 无论如何都添加到topic tracker
            if task.topic_id:
                self.topic_tracker.add_task(task)

            # 只有需要实际生成/修改代码时才转发给CR
            if need_forward_to_cr:
                # 查找处理该任务的CR
                cr_for_task = None
                for cr_bot_id, cr_info in self.crew_processes.items():
                    for opera_id, staff_ids in cr_info.staff_ids.items():
                        if task.response_staff_id in staff_ids:
                            cr_for_task = cr_info
                            break
                    if cr_for_task:
                        break

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
            """currently deprecated"""
            # 解析Tags中的资源信息
            tags = json.loads(task.parameters.get("tags", "{}"))
            resource_list = []
            version_id = None

            # 场景1：直接包含资源列表
            for tag_key in ["ResourcesForViewing", "ResourcesForIncarnating", "ResourcesMentionedFromViewer"]:
                if tag_key in tags:
                    resources = tags[tag_key].get("Resources", [])
                    resource_list.extend([{"file_path": res["Url"], "resource_id": res["ResourceId"]} for res in resources])

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
                    if topic_info and topic_info.current_version:
                        resource_list = [
                            {"file_path": res["file_path"], "resource_id": res["resource_id"]}
                            for res in topic_info.current_version.current_files
                        ]
                    elif topic_info:
                        # 如果current_version为空，记录警告
                        self.log.warning(f"主题 {version_id} 的current_version为空")
                except Exception as e:
                    self.log.error(f"获取版本资源失败: {str(e)}")
                    await self.task_queue.update_task_status(task.id, TaskStatus.FAILED)
                    return

            # 去重处理
            seen = set()
            unique_resources = [r for r in resource_list if not (r["resource_id"] in seen or seen.add(r["resource_id"]))]

            # 调用Crew进行任务分解
            analysis_result = (
                await IterationAnalyzerCrew()
                .crew()
                .kickoff_async(inputs={"iteration_requirement": task.parameters["text"], "resource_list": unique_resources})
            )

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
            # task_data = self._create_task_dto_for_cr(task, cm_staff_id)

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
            task_description = f"{task_state}"

            # 添加迭代标记
            iteration_tag = ";RESOURCE_ITERATION" if task.type == TaskType.RESOURCE_ITERATION else ""
            task_tags = f"TASK_ASSIGNMENT;TASK_ID:{task.id}{iteration_tag}"

            # 创建对话消息
            dialogue_data = DialogueForCreation(
                is_stage_index_null=False,
                staff_id=str(cm_staff_id),
                is_narratage=False,
                is_whisper=True,  # 设置为私聊
                text=task_description,
                # text=json.dumps(task_data),  # 将task_data转换为JSON字符串, 还需要转驼峰。
                tags=task_tags,
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
            # update_success, dialogue_success = await asyncio.gather(send_dialogue(),
            #                                                         # update_default_tags(), 暂时不做持久化
            #                                                         )
            dialogue_success = await send_dialogue()

            # 检查两个操作是否都成功
            if dialogue_success:
                self.log.info(f"已成功将任务 {task.id} 分配给CrewRunner {cr_bot_id}")
            else:
                self.log.warning(f"任务 {task.id} 分配给CrewRunner {cr_bot_id} 部分失败")

        except Exception as e:
            self.log.error(f"更新CrewRunner任务队列时发生错误: {str(e)}")

    def _create_task_dto_for_cr(self, task: BotTask, cm_staff_id: UUID) -> dict:
        """创建发送给CrewRunner的轻量级任务数据传输对象

        只包含CR执行任务所必需的字段，避免传输不必要的大量数据
        """
        # 基础必需字段
        task_dto = {
            "id": str(task.id),
            "type": task.type.name,
            "description": task.description,
            "sourceStaffId": str(cm_staff_id),
            "topicId": task.topic_id,
            "topicType": task.topic_type,
        }

        # 针对不同任务类型添加必要的parameters字段
        if task.parameters:
            # 提取所有任务类型都需要的基本参数
            essential_params = {
                "opera_id": task.parameters.get("opera_id"),
                "action": task.parameters.get("action"),
                "resource_id": task.parameters.get("resource_id"),
            }

            # 根据任务类型添加特定参数
            if task.type == TaskType.RESOURCE_GENERATION or task.type == TaskType.CODE_ITERATION:
                essential_params.update({
                    "file_path": task.parameters.get("file_path"),
                    "file_type": task.parameters.get("file_type"),
                    "description": task.parameters.get("description"),
                    "position": task.parameters.get("position"),
                })
            elif task.type == TaskType.CONVERSATION:
                # 对话类型任务可能需要的特定字段
                if "dialogue_context" in task.parameters:
                    dialogue_context = task.parameters.get("dialogue_context", {})
                    essential_params["dialogue_context"] = {
                        "text": dialogue_context.get("text"),
                        "type": dialogue_context.get("type"),
                        "intent": dialogue_context.get("intent"),
                    }

            task_dto["parameters"] = essential_params

        return task_dto

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

            # 查找并更新原始任务的result字段
            original_task = next((t for t in self.task_queue.tasks if t.id == UUID(task_id)), None)
            if original_task and result:
                original_task.result = result
                self.log.info(f"正在更新任务 {task_id} 的结果: {result}")

            # 更新当前回调任务的状态
            await self.task_queue.update_task_status(task_id=task.id, new_status=TaskStatus.COMPLETED)

            # 记录日志
            self.log.info(f"任务 {task_id} 已完成，结果: {result}")

        except Exception as e:
            self.log.error(f"处理任务回调时发生错误: {str(e)}")
            raise

    async def _handle_topic_completed(self, topic_id: str, opera_id: str):
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

            # 尝试使用TopicTracker获取该主题的已完成任务
            topic_info = self.topic_tracker.get_topic_info(topic_id)
            completed_tasks = []

            # 直接使用TopicTracker中的current_files
            if topic_info and topic_info.current_version and topic_info.current_version.current_files:
                # 资源列表已经是最新的，直接使用
                resources = self._build_resource_list_from_version(topic_info.current_version)
            else:
                # 仅在current_files为空时才回退到遍历任务的方式
                self.log.warning(f"主题 {topic_id} 的current_files为空，回退到遍历方式")

                if topic_id in self.topic_tracker._completed_tasks:
                    # 如果TopicTracker中有已完成任务的ID集合，通过ID查找完整任务对象
                    self.log.info(f"从TopicTracker缓存中获取主题 {topic_id} 的已完成任务ID")
                    completed_task_ids = self.topic_tracker._completed_tasks[topic_id]
                    completed_tasks = [
                        task
                        for task in self.task_queue.tasks
                        if task.id in completed_task_ids and task.type == TaskType.RESOURCE_CREATION
                    ]
                else:
                    # 回退到原有的遍历方式
                    self.log.info(f"TopicTracker缓存中不存在主题 {topic_id} 的已完成任务ID，回退到遍历方式")
                    completed_tasks = [
                        task
                        for task in self.task_queue.tasks
                        if task.topic_id == topic_id
                        and task.status == TaskStatus.COMPLETED
                        and task.type == TaskType.RESOURCE_CREATION
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

                # 从最新任务构建资源列表
                resources, html_files = self._build_resource_list_from_tasks(latest_tasks.values())

            # 添加空值检查
            if topic_info is None or topic_info.current_version is None:
                # 如果current_version为空，创建一个基本版本
                self.log.warning(f"主题 {topic_id} 的current_version为空，创建基本版本")
                if topic_info is not None:
                    topic_info.current_version = VersionMeta(
                        parent_version=None, modified_files=[], description="Auto-initialized on completion", current_files=[]
                    )
                    current_version = topic_info.current_version
                else:
                    self.log.error(f"找不到主题 {topic_id} 的信息")
                    return
            else:
                current_version = topic_info.current_version

            # 将VersionMeta对象转换为可序列化的字典
            current_version_dict = {
                "parent_version": current_version.parent_version,
                "modified_files": current_version.modified_files,
                "description": current_version.description,
                "current_files": current_version.current_files,
            }

            # 构建ResourcesForViewing标签的基本结构
            resources_tag = {
                "ResourcesForViewing": {
                    "VersionId": topic_id,
                    "Resources": [],
                    "CurrentVersion": current_version_dict,
                },
            }

            # 如果有修改过的文件，则只添加修改过的文件到Resources中
            if current_version.modified_files:
                # 提取modified_files中的file_path列表
                modified_file_paths = [item["file_path"] for item in current_version.modified_files if "file_path" in item]

                # 从resources中筛选出只在modified_file_paths中的资源
                modified_resources = [resource for resource in resources if resource.get("Url") in modified_file_paths]
                resources_tag["ResourcesForViewing"]["Resources"] = modified_resources
            else:
                # 如果没有修改过的文件，则添加所有resources并设置RemovingAllResources为True
                resources_tag["ResourcesForViewing"]["Resources"] = resources
                resources_tag["RemovingAllResources"] = True

            # 如果有deleted_files，则添加到RemovingResources中
            if hasattr(current_version, "deleted_files") and current_version.deleted_files:
                # 提取deleted_files中的file_path列表
                deleted_file_paths = [item["file_path"] for item in current_version.deleted_files if "file_path" in item]
                if deleted_file_paths:
                    resources_tag["RemovingResources"] = deleted_file_paths

            # 处理HTML文件导航逻辑
            self._add_navigation_index_if_needed(resources_tag)

            # 创建对话消息
            dialogue_data = DialogueForCreation(
                is_stage_index_null=False,
                staff_id=str(cm_staff_id),
                is_narratage=False,
                is_whisper=False,
                text=f"主题 {topic_id} 的所有资源已生成完成。",
                tags=json.dumps(resources_tag, ensure_ascii=False),
            )

            # 发送对话
            result = _SHARED_DIALOGUE_TOOL.run(action="create", opera_id=opera_id, data=dialogue_data)

            # 检查结果
            status_code, _ = ApiResponseParser.parse_response(result)
            if status_code not in [200, 201, 204]:
                self.log.error(f"发送主题 {topic_id} 完成对话失败, data:{dialogue_data}")
                return

            self.log.info(f"已发送主题 {topic_id} 完成对话，包含 {len(resources)} 个资源")

        except Exception as e:
            self.log.error(f"处理主题完成回调时发生错误: {str(e)}")

    def _build_resource_list_from_version(self, version: VersionMeta):
        """从版本元数据构建资源列表和HTML文件列表"""
        resources = []

        for file_entry in version.current_files:
            file_path = file_entry["file_path"]
            resource_id = file_entry["resource_id"]

            resource_info = {
                "Url": file_path,
                "ResourceId": resource_id,
                "ResourceCacheable": True,
            }
            resources.append(resource_info)

        return resources

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

            # 成功接受邀请后，为该Opera创建子Bot
            try:
                # 导入BotTool和创建子Bot的函数
                from src.crewai_ext.tools.opera_api.bot_api_tool import BotTool
                from src.core.bot_api_helper import create_child_bot, update_parent_bot_tags, get_child_bot_staff_info

                # 创建BotTool实例
                bot_tool = BotTool()

                # 获取Opera详细信息
                from src.crewai_ext.tools.opera_api.opera_api_tool import OperaTool
                from src.core.parser.api_response_parser import ApiResponseParser

                opera_tool = OperaTool()
                opera_result = opera_tool.run(action="get", opera_id=opera_id)
                status_code, opera_data = ApiResponseParser.parse_response(opera_result)

                if status_code != 200 or not opera_data:
                    self.log.error(f"获取Opera {opera_id} 信息失败，无法创建子Bot")
                    return

                # 构造Opera信息字典
                opera_info = {
                    "id": opera_id,
                    "name": opera_data.get("name", "未命名Opera"),
                    "description": opera_data.get("description", ""),
                }

                # 创建子Bot
                self.log.info(f"开始为Opera {opera_id} 创建子Bot...")
                child_bot_ids = await create_child_bot(bot_tool, opera_info, str(self.bot_id), self.log)

                if child_bot_ids:
                    # 更新父Bot的标签，记录子Bot列表
                    await update_parent_bot_tags(bot_tool, str(self.bot_id), child_bot_ids, self.log)

                    # 为每个子Bot获取staff信息，并添加到crew_processes中
                    for child_bot_id in child_bot_ids:
                        # 获取子Bot的配置
                        bot_info = bot_tool.run(action="get", bot_id=child_bot_id)
                        _, bot_data = ApiResponseParser.parse_response(bot_info)

                        # 提取CrewConfig
                        crew_config = {}
                        if bot_data.get("defaultTags"):
                            try:
                                tags = json.loads(bot_data["defaultTags"])
                                crew_config = tags.get("CrewConfig", {})
                            except json.JSONDecodeError:
                                self.log.warning(f"解析子Bot {child_bot_id} 的defaultTags失败")

                        # 获取staff信息
                        staff_info = await get_child_bot_staff_info(bot_tool, child_bot_id, self.log)

                        if staff_info:
                            # 提取所有opera的staff_ids和roles
                            staff_ids = {}
                            roles = {}
                            opera_ids = []

                            for opera_id_str, info in staff_info.items():
                                opera_ids.append(UUID(opera_id_str))
                                staff_ids[UUID(opera_id_str)] = info["staff_ids"]
                                roles[UUID(opera_id_str)] = info.get("roles", [])

                            # 创建CrewProcessInfo
                            process_info = CrewProcessInfo(
                                process=None,  # 只保存信息，不创建进程
                                bot_id=UUID(child_bot_id),
                                crew_config=crew_config,
                                opera_ids=opera_ids,
                                roles=roles,
                                staff_ids=staff_ids,
                            )

                            # 添加到crew_processes
                            self.crew_processes[UUID(child_bot_id)] = process_info
                            self.log.info(f"已将子Bot {child_bot_id} 添加到crew_processes中")

                self.log.info(f"成功为Opera {opera_id} 创建了 {len(child_bot_ids)} 个子Bot")

            except Exception as e:
                self.log.error(f"创建子Bot时发生错误: {str(e)}")
                self.log.exception("详细错误信息:")

        except ValueError as e:
            self.log.error(f"参数验证失败: {str(e)}")
        except Exception as e:
            self.log.error(f"自动接受邀请失败: {str(e)}")
            self.log.exception("详细错误信息:")

    def _add_navigation_index_if_needed(self, resources_tag):
        """如果存在index.html文件，添加导航索引
        TODO: 可以用一个小模型来结合对话内容来判断跳转哪个索引

        Args:
            resources_tag: 资源标签字典
        """
        # 获取resources列表
        resources = resources_tag["ResourcesForViewing"].get("Resources", [])
        html_candidates = []

        # 第一轮遍历：查找index.html并记录所有html文件
        for index, resource in enumerate(resources):
            url = resource.get("Url", "").lower()
            if url.endswith(".html"):
                html_candidates.append(index)
                if url.endswith("/index.html") or url == "index.html":
                    # 直接使用resource列表中的索引
                    resources_tag["ResourcesForViewing"]["NavigateIndex"] = index
                    return

        # 第二轮遍历：如果没有index.html，选择第一个html文件
        if html_candidates:
            resources_tag["ResourcesForViewing"]["NavigateIndex"] = html_candidates[0]

    def _build_resource_list_from_tasks(self, tasks):
        """从任务列表构建资源列表和HTML文件列表

        Args:
            tasks: 任务列表

        Returns:
            tuple: (resources列表, html_files列表)
        """
        resources = []
        html_files = []  # 存储所有HTML文件路径

        for task in tasks:
            if task.result and isinstance(task.result, dict):
                file_path = task.parameters.get("file_path", "")
                resource_id = task.result.get("resource_id", "")

                if not file_path or not resource_id:
                    continue

                resource_info = {
                    "Url": file_path,
                    "ResourceId": resource_id,
                    "ResourceCacheable": True,
                }
                resources.append(resource_info)

                # 收集HTML文件路径用于导航判断
                if file_path.lower().endswith(".html"):
                    html_files.append(file_path)

        return resources, html_files
