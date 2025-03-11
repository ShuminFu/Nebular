from dataclasses import dataclass
from typing import Dict, Set, Optional, List, Callable, Awaitable, Literal, Any
from uuid import UUID
import json
import logging

from src.core.task_utils import BotTask, TaskStatus, TaskType

# 定义资源操作类型
ResourceAction = Literal["unchange", "delete", "update", "create"]

# 获取日志记录器
logger = logging.getLogger(__name__)


@dataclass
class VersionMeta:
    parent_version: Optional[str]  # 父版本ID
    modified_files: List[Dict[str, str]]  # 本次修改的文件列表，包含file_path和resource_id
    description: str  # 修改原因/用户反馈/任务描述
    current_files: List[Dict[str, str]]  # 当前版本的完整文件列表，包含file_path和resource_id
    deleted_files: List[Dict[str, str]] = None  # 本次删除的文件列表，包含file_path和resource_id


# TODO:delta changes fields for diff modification such as line 1-20

@dataclass
class TopicInfo:
    """主题信息"""
    tasks: Set[UUID]  # 任务ID集合
    type: str  # 主题类型
    status: str  # 主题状态
    opera_id: str  # Opera ID
    current_version: Optional[VersionMeta] = None  # 当前版本
    expected_creation_count: int = 0  # 由generation任务预报的预期创建任务数量
    actual_creation_count: int = 0  # 实际添加到tracker的创建任务数量
    completed_creation_count: int = 0  # 已完成的创建任务数量


# 定义回调类型
TopicCompletionCallback = Callable[[str, str], Awaitable[None]]  # topic_id, opera_id


class TopicTracker:
    """主题追踪器，负责管理主题状态和任务关系"""

    def __init__(self):
        self.topics: Dict[str, TopicInfo] = {}
        self._completion_callbacks: List[TopicCompletionCallback] = []
        self._completed_tasks: Dict[str, Set[UUID]] = {}  # topic_id -> completed task ids
        self._pending_resource_tasks: Dict[UUID, str] = {}  # task_id -> file_path，存储等待resource_id的任务
        self._resource_actions: Dict[UUID, Dict[str, str]] = {}  # task_id -> {file_path: action}，存储资源操作类型
        self._processing_version_ids = set()  # 用于避免递归循环

    def _extract_task_params(self, task: BotTask) -> Dict[str, Any]:
        """从任务中提取常用参数

        Args:
            task: 任务对象

        Returns:
            Dict[str, Any]: 常用参数字典
        """
        params = task.parameters
        return {
            "opera_id": params.get("opera_id"),
            "file_path": params.get("file_path"),
            "resource_id": params.get("resource_id"),
            "action": params.get("action", "").lower(),
            "description": params.get("description", ""),
            "parent_topic_id": params.get("parent_topic_id"),
            "parent_version_id": params.get("parent_version_id"),
            "expected_files_count": params.get("expected_files_count", 1),
            "code_details": params.get("code_details", {}),
        }

    def on_completion(self, callback: TopicCompletionCallback):
        """注册主题完成回调"""
        self._completion_callbacks.append(callback)

    def add_task(self, task: BotTask):
        """添加任务到主题"""
        if not task.topic_id:
            return

        # 提取任务参数
        params = self._extract_task_params(task)

        # 创建新主题
        if task.topic_id not in self.topics:
            topic_info = TopicInfo(
                tasks=set(),
                type=task.topic_type,
                status="active",
                opera_id=params["opera_id"],
                current_version=None,
            )
            self.topics[task.topic_id] = topic_info

            # 初始化当前版本 - 同时支持parent_topic_id和parent_version_id参数
            parent_version_id = params["parent_topic_id"] or params["parent_version_id"]
            if parent_version_id:
                parent_version = None if parent_version_id == "0" else parent_version_id

                # 构建更全面的描述，优先使用项目描述和需求列表
                description = params["description"] or ""

                # 如果有项目描述，将其添加到描述中
                if "project_description" in params:
                    description = params["code_details"]["project_description"]

                # 如果有需求列表，将其添加到描述中
                if "requirements" in params["code_details"]:
                    requirements_str = ", ".join(params["code_details"]["requirements"])
                    if description:
                        description += f" 需求：{requirements_str}"
                    else:
                        description = f"需求：{requirements_str}"

                # 如果仍然没有描述，使用默认值
                if not description:
                    description = "Initial version"

                self.topics[task.topic_id].current_version = VersionMeta(
                    parent_version=parent_version, modified_files=[], description=description, current_files=[], deleted_files=[]
                )

                # 如果有父版本，加载父版本资源列表
                if parent_version and parent_version != "0":
                    self._load_parent_version_resources(task.topic_id, parent_version, params["opera_id"])

            self._completed_tasks[task.topic_id] = set()

        topic = self.topics[task.topic_id]
        topic.tasks.add(task.id)

        # 检查任务是否包含action信息
        action = params["action"]
        file_path = params["file_path"]
        has_action = bool(action and file_path)

        if has_action:
            # 处理包含action的任务
            self._process_resources_with_actions(task)
        # 更新任务计数：根据任务类型更新对应的计数器
        elif task.type == TaskType.RESOURCE_GENERATION:
            # 对于不包含action的RESOURCE_GENERATION任务，增加预期创建任务数量
            expected_files_count = params["expected_files_count"]
            topic.expected_creation_count += expected_files_count
        elif task.type == TaskType.RESOURCE_CREATION:
            # 对于RESOURCE_CREATION任务，增加实际创建任务数量
            topic.actual_creation_count += 1

        # 处理文件路径更新
        resource_id = params["resource_id"]

        # 对于资源创建任务，先记录file_path，等任务完成后再更新resource_id
        if task.type == TaskType.RESOURCE_CREATION and file_path:
            self._pending_resource_tasks[task.id] = file_path

            # 如果已有resource_id，直接更新映射关系；否则等待任务完成后更新
            if resource_id:
                self._update_file_mapping(topic, file_path, resource_id)
        # 对于非资源创建任务且不包含action的任务，直接更新file_path和resource_id的映射
        elif file_path and resource_id and not has_action:
            self._update_file_mapping(topic, file_path, resource_id)

    def _process_resources_with_actions(self, task: BotTask):
        """处理任务中包含action的resources"""
        if not task.topic_id:
            return

        topic = self.topics[task.topic_id]
        # 提取任务参数
        params = self._extract_task_params(task)
        file_path = params["file_path"]
        action = params["action"]

        if not file_path or not action:
            return

        # 记录资源操作类型
        resource_actions = {file_path: action}

        # 如果是删除操作，先处理
        if action == "delete":
            self._mark_resource_as_deleted(topic, file_path)
        else:
            # 处理其他操作
            self._process_single_resource_action(topic, task, file_path, action)

        # 存储任务的资源操作
        self._resource_actions[task.id] = resource_actions

    def _process_single_resource_action(self, topic: TopicInfo, task: BotTask, file_path: str, action: str):
        """处理单个资源的action"""
        params = self._extract_task_params(task)
        resource_id = params["resource_id"]

        if action == "unchange":
            # 不变的资源，直接从父版本复制
            pass  # 父版本资源已在_load_parent_version_resources中加载
        elif action == "update":
            # 更新资源，统一使用_pending_resource_tasks的逻辑
            # 不直接使用父版本的resource_id，等待更新操作完成后获取新的resource_id
            self._pending_resource_tasks[task.id] = file_path
            topic.expected_creation_count += 1
        elif action == "create":
            # 新建资源，与现有逻辑一致
            self._pending_resource_tasks[task.id] = file_path
            topic.expected_creation_count += 1

    def _load_parent_version_resources(self, topic_id: str, parent_version_id: str, opera_id: str = None):
        """从父版本加载资源列表

        Args:
            topic_id: 当前主题ID
            parent_version_id: 父版本ID
            opera_id: Opera ID，用于调用对话工具
        """
        # 处理特殊情况，避免递归循环
        if parent_version_id in self._processing_version_ids:
            logger.warning(f"检测到递归循环，跳过版本ID {parent_version_id}")
            return

        # 标记正在处理的版本ID，防止递归循环
        self._processing_version_ids.add(parent_version_id)

        try:
            # 首先从内存中尝试获取资源
            parent_topic = self.get_topic_info(parent_version_id)
            if parent_topic and parent_topic.current_version and parent_topic.current_version.current_files:
                current_topic = self.topics[topic_id]
                if current_topic.current_version:
                    # 将父版本的current_files复制到当前版本，但不覆盖已有的文件
                    parent_files = parent_topic.current_version.current_files

                    # 如果当前版本没有文件列表，则初始化为空列表
                    if not current_topic.current_version.current_files:
                        current_topic.current_version.current_files = []

                    # 创建现有文件路径的集合，用于快速查找
                    existing_file_paths = {entry["file_path"] for entry in current_topic.current_version.current_files}

                    # 添加父版本中的文件，跳过已存在的
                    for parent_file in parent_files:
                        if parent_file["file_path"] not in existing_file_paths:
                            current_topic.current_version.current_files.append(parent_file.copy())

                    return

            # 如果内存中没有找到或资源为空，尝试从对话工具获取
            if opera_id:
                # 从对话工具获取资源
                resources = self.get_resources_by_version_ids([parent_version_id], opera_id)

                if resources:
                    current_topic = self.topics[topic_id]
                    if current_topic.current_version:
                        # 如果当前版本没有文件列表，则初始化为空列表
                        if not current_topic.current_version.current_files:
                            current_topic.current_version.current_files = []

                        # 创建现有文件路径的集合，用于快速查找
                        existing_resources = {entry["resource_id"] for entry in current_topic.current_version.current_files}

                        # 添加从对话工具获取的文件，跳过已存在的
                        for resource in resources:
                            if resource["resource_id"] not in existing_resources:
                                current_topic.current_version.current_files.append(resource.copy())
        finally:
            # 处理完成后移除标记
            if parent_version_id in self._processing_version_ids:
                self._processing_version_ids.remove(parent_version_id)

    def _mark_resource_as_deleted(self, topic: TopicInfo, file_path: str):
        """标记资源为已删除"""
        if not topic.current_version:
            return

        # 初始化deleted_files列表
        if topic.current_version.deleted_files is None:
            topic.current_version.deleted_files = []

        # 从current_files中找到对应的资源信息
        resource_entry = None
        files_to_remove = []

        for i, entry in enumerate(topic.current_version.current_files):
            if entry["file_path"] == file_path:
                resource_entry = entry.copy()
                # 标记要移除的索引
                files_to_remove.append(i)

        # 从high到low删除，避免索引变化问题
        for i in sorted(files_to_remove, reverse=True):
            topic.current_version.current_files.pop(i)

        # 如果找到对应资源，添加到deleted_files
        if resource_entry:
            topic.current_version.deleted_files.append(resource_entry)

    def _update_file_mapping(self, topic: TopicInfo, file_path: str, resource_id: str):
        """更新文件路径与资源ID的映射关系"""
        file_entry = {"file_path": file_path, "resource_id": resource_id}

        # 检查是否为更新操作，通过判断文件是否已存在于当前版本的文件列表中
        is_update = False
        if topic.current_version is not None and topic.current_version.current_files:
            for entry in topic.current_version.current_files:
                if entry["file_path"] == file_path:
                    is_update = True
                    break

        # 更新当前版本，添加空值检查
        if topic.current_version is not None:
            # 更新modified_files和current_files列表
            for files_list in [topic.current_version.modified_files, topic.current_version.current_files]:
                found = False
                for i, entry in enumerate(files_list):
                    if entry["file_path"] == file_path:
                        # 如果存在，更新resource_id
                        files_list[i]["resource_id"] = resource_id
                        found = True
                        break

                # 如果不存在且应该添加，则添加新条目
                if not found:
                    if files_list is topic.current_version.current_files or (
                        is_update and files_list is topic.current_version.modified_files
                    ):
                        files_list.append(file_entry)
        else:
            # 如果current_version为None，则初始化一个默认版本
            topic.current_version = VersionMeta(
                parent_version=None,
                modified_files=[file_entry],
                description="Auto-initialized version",
                current_files=[file_entry],
                deleted_files=[],
            )

    async def update_task_status(self, task_id: UUID, status: TaskStatus, task: Optional[BotTask] = None):
        """
        更新任务状态并检查主题完成情况

        Args:
            task_id: 任务ID
            status: 新状态
            task: 可选的完整任务对象，用于获取任务结果
        """
        # 查找任务所属的主题
        topic_id = None
        for tid, topic in self.topics.items():
            if task_id in topic.tasks:
                topic_id = tid
                break

        if not topic_id:
            return

        # 获取任务类型和资源信息
        task_type = None
        has_resource_actions = False
        params = {}
        if task is not None:
            task_type = task.type
            params = self._extract_task_params(task)
            resources = task.parameters.get("resources", [])
            has_resource_actions = resources and any("action" in resource for resource in resources)

        # 如果是资源创建任务且已完成，处理resource_id更新
        if status == TaskStatus.COMPLETED and task_id in self._pending_resource_tasks:
            # 通过topic_id找到任务所属的主题
            topic = self.topics[topic_id]

            # 如果传入了任务对象，直接使用
            if task is not None:
                if (result := task.result) and isinstance(result, dict) and (resource_id := result.get("resource_id")):
                    file_path = self._pending_resource_tasks[task_id]
                    # 更新文件映射
                    self._update_file_mapping(topic, file_path, resource_id)
                    # 从待处理列表中移除
                    self._pending_resource_tasks.pop(task_id)

        # 如果是带有资源操作的任务且已完成，处理资源操作
        if status == TaskStatus.COMPLETED and task_id in self._resource_actions:
            if task is not None and (result := task.result) and isinstance(result, dict):
                topic = self.topics[topic_id]
                resource_id = result.get("resource_id")
                file_path = params["file_path"]

                if resource_id and file_path:
                    actions = self._resource_actions[task_id]
                    action = actions.get(file_path)

                    if action in ["update", "create"]:
                        self._update_file_mapping(topic, file_path, resource_id)

                    # 处理完毕后清理
                    if file_path in actions:
                        actions.pop(file_path)
                        if not actions:
                            self._resource_actions.pop(task_id)

        # 如果任务完成，记录并更新计数
        if status == TaskStatus.COMPLETED:
            topic = self.topics[topic_id]
            self._completed_tasks[topic_id].add(task_id)

            # 如果是RESOURCE_CREATION任务，增加已完成创建任务计数并检查完成情况
            if task_type == TaskType.RESOURCE_CREATION:
                topic.completed_creation_count += 1
                # 只有CREATION类任务完成才会触发主题完成检查
                await self._check_topic_completion(topic_id)
            # 对于带有资源操作的任务，检查是否还有待处理的资源任务
            elif has_resource_actions:
                # 检查与当前主题相关的待处理资源任务是否都已完成
                has_pending_tasks = False
                for pending_task_id, _ in list(self._pending_resource_tasks.items()):
                    if pending_task_id in topic.tasks:
                        has_pending_tasks = True
                        break

                if not has_pending_tasks:
                    await self._check_topic_completion(topic_id)

    async def _check_topic_completion(self, topic_id: str):
        """检查主题是否全部完成

        主题完成的判断逻辑有三种方式，按优先级排序：
        1. 如果设置了预期创建任务数量（expected_creation_count > 0），则检查已完成的创建任务是否达到预期数量
        2. 如果没有预期数量，但有实际添加的创建任务（actual_creation_count > 0），则检查是否所有创建任务都已完成
        3. 作为后备机制，检查主题的所有任务是否都已完成
        """
        topic = self.topics.get(topic_id)
        if not topic or topic.status != "active":
            return

        # 首先检查是否有预期数量
        if topic.expected_creation_count > 0:
            # 如果有预期数量，检查已完成的创建任务是否达到预期数量
            if topic.completed_creation_count >= topic.expected_creation_count:
                # 达到预期数量，标记为完成
                await self._complete_topic(topic_id, topic)
        # 如果没有预期数量或预期数量为0，检查是否所有实际添加的创建任务都已完成
        elif topic.actual_creation_count > 0 and topic.completed_creation_count >= topic.actual_creation_count:
            # 所有实际添加的创建任务都已完成，标记为完成
            await self._complete_topic(topic_id, topic)
        # 保留原有的检查逻辑作为兼容性后备
        elif topic.tasks == self._completed_tasks[topic_id]:
            # 所有任务都已完成，标记为完成
            await self._complete_topic(topic_id, topic)

    async def _complete_topic(self, topic_id: str, topic: TopicInfo):
        """将主题标记为完成并触发回调"""
        # 通知所有回调
        for callback in self._completion_callbacks:
            await callback(topic_id, topic.opera_id)

        # 更新主题状态
        topic.status = "completed"

    def get_topic_info(self, topic_id: str) -> Optional[TopicInfo]:
        """获取主题信息"""
        return self.topics.get(topic_id)

    def get_resources_by_version_ids(self, version_ids: List[str], opera_id: str = None) -> List[Dict[str, str]]:
        """获取多个版本ID对应的资源列表

        首先尝试从内存中获取资源，如果未找到则通过Dialog API工具查找

        Args:
            version_ids: 版本ID列表
            opera_id: Opera ID，用于调用对话工具

        Returns:
            list: 资源列表，格式为[{'file_path': 'path', 'resource_id': 'id'}]
        """

        resources = []

        # 如果内存中没有找到，且提供了opera_id，则尝试通过对话工具获取
        if not opera_id:
            return resources

        # 通过Dialog API工具查找资源
        logger.info(f"通过对话工具查找版本ID对应的资源: {version_ids}")

        try:
            from src.crewai_ext.tools.opera_api.dialogue_api_tool import _SHARED_DIALOGUE_TOOL

            all_resources = []

            # 遍历每个版本ID查找相关对话
            for version_id in version_ids:
                # 构建查询条件，寻找包含指定VersionId的对话
                filter_data = {
                    "action": "get_filtered",
                    "opera_id": opera_id,
                    "data": {
                        "includes_staff_id_null": True,
                        "includes_stage_index_null": True,
                        "includes_narratage": True,
                        "tag_node_values": [{"path": "$.ResourcesForViewing.VersionId", "value": version_id, "type": "String"}],
                    },
                }

                # 调用DialogueTool查询对话
                result = _SHARED_DIALOGUE_TOOL.run(**filter_data)

                if result:
                    try:
                        from src.core.parser.api_response_parser import ApiResponseParser

                        status_code, parsed_data = ApiResponseParser.parse_response(result)
                        if status_code == -1:
                            continue
                        dialogues = parsed_data
                        for dialogue in dialogues:
                            if "tags" in dialogue:
                                try:
                                    # 从tags中提取资源信息
                                    tags_str = dialogue.get("tags", "{}")
                                    if isinstance(tags_str, str):
                                        tags = json.loads(tags_str)
                                    else:
                                        tags = tags_str

                                    # 尝试从ResourcesForViewing.Resources中获取资源
                                    resources_viewing = tags.get("ResourcesForViewing", {})
                                    if resources_viewing:
                                        # 从Resources列表获取资源
                                        resources_list = resources_viewing.get("Resources", [])
                                        for resource in resources_list:
                                            if "Url" in resource and "ResourceId" in resource:
                                                url = resource["Url"]
                                                # 处理URL格式，提取文件路径
                                                file_path = url
                                                if not file_path.startswith("/"):
                                                    # 提取路径部分
                                                    file_path = (
                                                        "/" + file_path.split("/", 1)[-1] if "/" in file_path else file_path
                                                    )

                                                all_resources.append({
                                                    "file_path": file_path,
                                                    "resource_id": resource["ResourceId"],
                                                })

                                        # 尝试从CurrentVersion中获取资源
                                        current_version = resources_viewing.get("CurrentVersion")
                                        if current_version and "current_files" in current_version:
                                            cv_files = current_version.get("current_files", [])
                                            for file in cv_files:
                                                if "file_path" in file and "resource_id" in file:
                                                    all_resources.append(file.copy())

                                    # 直接查找CurrentVersion
                                    if "CurrentVersion" in tags:
                                        current_version = tags.get("CurrentVersion")
                                        if current_version:
                                            # 从Files列表获取资源
                                            files = current_version.get("Files", [])
                                            for file in files:
                                                if "FilePath" in file and "ResourceId" in file:
                                                    all_resources.append({
                                                        "file_path": file["FilePath"],
                                                        "resource_id": file["ResourceId"],
                                                    })

                                            # 也尝试从current_files获取资源
                                            cv_files = current_version.get("current_files", [])
                                            for file in cv_files:
                                                if "file_path" in file and "resource_id" in file:
                                                    all_resources.append(file.copy())
                                except json.JSONDecodeError:
                                    logger.warning(f"解析对话tags失败: {dialogue.get('tags')}")
                                    continue
                                except Exception as e:
                                    logger.error(f"处理对话tags时出错: {str(e)}")
                                    continue
                    except json.JSONDecodeError:
                        logger.warning(f"解析对话响应失败: {result}")
                    except Exception as e:
                        logger.error(f"处理对话响应时出错: {str(e)}")

            # 去重，避免重复资源
            unique_resources = []
            resource_ids = set()

            for resource in all_resources:
                resource_id = resource.get("resource_id")
                if resource_id and resource_id not in resource_ids:
                    resource_ids.add(resource_id)
                    unique_resources.append(resource)

            return unique_resources

        except ImportError:
            logger.error("无法导入对话工具，请确保已安装相关依赖")
            return resources
        except Exception as e:
            logger.error(f"通过对话工具获取资源时出错: {str(e)}")
            return resources
