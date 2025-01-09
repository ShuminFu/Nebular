""" Opera SignalR 任务队列的数据模型定义。"""

from pydantic import Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
from enum import IntEnum
from src.opera_service.api.models import BotForUpdate, CamelBaseModel
from src.crewai_ext.tools.opera_api.bot_api_tool import _SHARED_BOT_TOOL
from src.core.api_response_parser import ApiResponseParser
import json


class TaskPriority(IntEnum):
    """任务优先级枚举"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


class TaskType(IntEnum):
    """任务类型枚举"""
    # 基础对话任务
    CONVERSATION = 10  # 基础对话处理，不一定需要回复，比如CrewRunner仅回复被Mentioned或者Whispered的对话
    CHAT_PLANNING = 11  # 对话策略规划
    CHAT_RESPONSE = 12  # 对话响应生成

    # 分析类任务
    ANALYSIS = 20  # 基础分析
    INTENT_ANALYSIS = 21  # 意图分析
    CONTEXT_ANALYSIS = 22  # 上下文分析，比如需要额外的RAG BOT/SEARCH BOT的帮助来收集上下文

    # 执行类任务
    EXECUTION = 30  # 基础执行
    TOOL_EXECUTION = 31  # 工具调用
    API_CALL = 32  # API调用
    CALLBACK = 33  # 任务回调

    # 管理类任务
    SYSTEM = 40  # 系统任务
    CREW_LIFECYCLE = 41  # CrewRunner的生命周期管理
    STAGE_MANAGEMENT = 42  # Opera Stage 管理
    ROLE_ASSIGNMENT = 43  # 发言角色分配

    # 资源管理任务

    RESOURCE_CREATION = 50  # 资源持久化任务：将生成的代码保存为Opera平台的资源文件, 需要调用工具创建资源, 由cm处理

    RESOURCE_GENERATION = 51  # LLM代码生成任务：通过AI生成代码文件内容, 由cr处理


class TaskStatus(IntEnum):
    """任务状态枚举"""
    PENDING = 1
    RUNNING = 2
    COMPLETED = 3
    FAILED = 4
    BLOCKED = 5


class BotTask(CamelBaseModel):
    """任务模型"""
    id: UUID = Field(default_factory=lambda: UUID(int=uuid4().int), description="任务唯一标识")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone(timedelta(hours=8))),
        description="创建时间 (UTC+8)"
    )
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")

    # 任务基本信息
    priority: TaskPriority = Field(default=TaskPriority.NORMAL, description="任务优先级")
    type: TaskType = Field(..., description="任务类型")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")

    # 任务内容
    description: str = Field(..., description="任务描述,由intent而来")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="任务参数，由processing_dialogue的text以及context组成")

    # 来源信息
    source_dialogue_index: Optional[int] = Field(default=None, description="源对话索引")
    response_staff_id: Optional[UUID] = Field(default=None, description="响应Staff ID")
    source_staff_id: Optional[UUID] = Field(default=None, description="源Staff ID，用于追踪任务的发起者")

    # 执行信息
    progress: int = Field(default=0, description="任务进度(0-100)，暂时无用")
    result: Optional[Any] = Field(default=None, description="任务结果")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    retry_count: int = Field(default=0, description="重试次数，暂时无用")
    last_retry_at: Optional[datetime] = Field(default=None, description="最后重试时间，暂时无用")


class PersistentTaskState(BotTask):
    """持久化的任务状态模型

    继承自BotTask，但只保留需要持久化的关键状态信息。
    """
    class Config:
        # 只包含显式声明的字段
        extra = "forbid"

    # 任务标识（必需）
    id: UUID = Field(..., description="任务唯一标识")
    created_at: datetime = Field(..., description="创建时间")

    # 任务基本信息（必需）
    priority: TaskPriority = Field(..., description="任务优先级")
    type: TaskType = Field(..., description="任务类型")
    status: TaskStatus = Field(..., description="任务状态")

    # 任务内容（必需）
    description: str = Field(..., description="任务描述")
    parameters: Dict[str, Any] = Field(..., description="任务参数")

    # 来源信息（可选）
    source_dialogue_index: Optional[int] = Field(default=None, description="源对话索引")
    response_staff_id: Optional[UUID] = Field(default=None, description="响应Staff ID")
    source_staff_id: Optional[UUID] = Field(default=None, description="源Staff ID")

    # 执行状态（必需）
    progress: int = Field(..., description="任务进度")
    result: Optional[Any] = Field(default=None, description="任务结果")
    error_message: Optional[str] = Field(default=None, description="错误信息")

    @classmethod
    def from_bot_task(cls, task: BotTask) -> "PersistentTaskState":
        """从BotTask创建持久化状态"""
        return cls(
            id=task.id,
            created_at=task.created_at,
            priority=task.priority,
            type=task.type,
            status=task.status,
            description=task.description,
            parameters=task.parameters,
            source_dialogue_index=task.source_dialogue_index,
            response_staff_id=task.response_staff_id,
            source_staff_id=task.source_staff_id,
            progress=task.progress,
            result=task.result,
            error_message=task.error_message
        )


class BotTaskQueue(CamelBaseModel):
    """任务队列模型"""
    tasks: List[BotTask] = Field(default_factory=list, description="任务列表")
    status_counter: Dict[str, int] = Field(
        default_factory=lambda: {status.name.lower(): 0 for status in TaskStatus},
        description="状态计数器"
    )
    bot_id: UUID = Field(..., description="Bot ID")

    async def _persist_to_api(self) -> None:
        """将任务队列状态持久化到API

        将任务队列中的每个任务以PersistentTaskState的形式持久化到Bot的DefaultTags中。
        步骤：
        1. 获取Bot当前的DefaultTags
        2. 更新DefaultTags中的任务状态
        3. 将更新后的DefaultTags保存回API
        """
        try:
            # 获取当前bot的信息
            get_result = _SHARED_BOT_TOOL.run(
                action="get",
                bot_id=self.bot_id
            )

            # 解析API响应
            status_code, bot_data = ApiResponseParser.parse_response(get_result)
            if status_code != 200 or not bot_data:
                print(f"获取Bot {self.bot_id} 失败")
                return

            # 获取当前DefaultTags
            try:
                current_tags = json.loads(bot_data.get("defaultTags", "{}"))
            except json.JSONDecodeError:
                current_tags = {}

            # 将任务转换为持久化状态
            task_states = [
                PersistentTaskState.from_bot_task(task).model_dump(by_alias=True)
                for task in self.tasks
            ]

            # 更新DefaultTags
            current_tags["TaskStates"] = task_states

            # 更新bot的DefaultTags
            update_result = _SHARED_BOT_TOOL.run(
                action="update",
                bot_id=self.bot_id,
                data=BotForUpdate(
                    name=None,
                    is_description_updated=False,
                    description=None,
                    is_call_shell_on_opera_started_updated=False,
                    call_shell_on_opera_started=None,
                    is_default_tags_updated=True,
                    default_tags=json.dumps(current_tags),
                    is_default_roles_updated=False,
                    default_roles=None,
                    is_default_permissions_updated=False,
                    default_permissions=None
                )
            )

            # 检查更新结果
            status_code, _ = ApiResponseParser.parse_response(update_result)
            if status_code not in [200, 204]:
                print(f"更新Bot {self.bot_id} 的DefaultTags失败")

        except Exception as e:
            print(f"持久化Bot {self.bot_id} 的任务状态时发生错误: {str(e)}")

    @classmethod
    def create(cls, bot_id: UUID, **kwargs) -> "BotTaskQueue":
        """创建任务队列的工厂方法

        Args:
            bot_id: Bot ID
            **kwargs: 其他参数

        Returns:
            BotTaskQueue: 新创建的任务队列实例
        """
        return cls(bot_id=bot_id, **kwargs)

    @classmethod
    async def restore_from_api(cls, bot_id: UUID, **kwargs) -> "BotTaskQueue":
        """从API恢复任务队列状态的工厂方法

        从Bot的DefaultTags中恢复持久化的任务状态。

        Args:
            bot_id: Bot ID
            **kwargs: 配置参数，可能包括时间范围、过滤条件等

        Returns:
            BotTaskQueue: 恢复的任务队列实例
        """
        try:
            # 创建一个新的任务队列实例
            queue = cls(bot_id=bot_id, **kwargs)

            # 获取Bot信息
            get_result = _SHARED_BOT_TOOL.run(
                action="get",
                bot_id=bot_id
            )

            # 解析API响应
            status_code, bot_data = ApiResponseParser.parse_response(get_result)
            if status_code != 200 or not bot_data:
                print(f"获取Bot {bot_id} 失败")
                return queue

            # 获取DefaultTags中的任务状态
            try:
                current_tags = json.loads(bot_data.get("defaultTags", "{}"))
                task_states = current_tags.get("TaskStates", [])
            except json.JSONDecodeError:
                print(f"解析Bot {bot_id} 的DefaultTags失败")
                return queue

            # 将持久化状态转换为BotTask对象
            for task_state in task_states:
                try:
                    # 创建完整的BotTask对象
                    task = BotTask(
                        id=task_state["id"],
                        created_at=datetime.fromisoformat(task_state["createdAt"]),
                        priority=TaskPriority(task_state["priority"]),
                        type=TaskType(task_state["type"]),
                        status=TaskStatus(task_state["status"]),
                        description=task_state["description"],
                        parameters=task_state["parameters"],
                        source_dialogue_index=task_state.get("sourceDialogueIndex"),
                        response_staff_id=task_state.get("responseStaffId"),
                        source_staff_id=task_state.get("sourceStaffId"),
                        progress=task_state["progress"],
                        result=task_state.get("result"),
                        error_message=task_state.get("errorMessage")
                    )
                    queue.tasks.append(task)

                    # 更新状态计数器
                    queue.status_counter[task.status.name.lower()] += 1

                except (KeyError, ValueError) as e:
                    print(f"转换任务状态失败: {str(e)}")
                    continue

            return queue

        except Exception as e:
            print(f"恢复Bot {bot_id} 的任务状态时发生错误: {str(e)}")
            # 发生错误时返回空队列
            return cls(bot_id=bot_id, **kwargs)

    async def add_task(self, task: Union[BotTask, List[BotTask]]) -> None:
        """添加任务并更新计数器

        Args:
            task: 单个BotTask对象或BotTask列表
        """
        if isinstance(task, list):
            # 如果是列表，则逐个添加任务
            for t in task:
                self.tasks.append(t)
                self.status_counter[t.status.name.lower()] += 1
        else:
            # 如果是单个任务，直接添加
            self.tasks.append(task)
            self.status_counter[task.status.name.lower()] += 1

        # 添加任务后持久化
        await self._persist_to_api()

    async def update_task_status(self, task_id: UUID, new_status: TaskStatus) -> None:
        """更新任务状态并维护计数器"""
        for task in self.tasks:
            if task.id == task_id:
                old_status = task.status
                task.status = new_status

                # 更新时间戳
                if new_status == TaskStatus.RUNNING:
                    task.started_at = datetime.now(timezone(timedelta(hours=8)))
                elif new_status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    task.completed_at = datetime.now(timezone(timedelta(hours=8)))

                # 更新计数器
                self.status_counter[old_status.name.lower()] -= 1
                self.status_counter[new_status.name.lower()] += 1
                # 状态更新后持久化
                await self._persist_to_api()
                break

    def get_next_task(self) -> Optional[BotTask]:
        """获取下一个待处理的任务（按优先级排序，同优先级按创建时间FIFO）"""
        pending_tasks = [
            task for task in self.tasks
            if task.status == TaskStatus.PENDING
        ]
        if not pending_tasks:
            return None

        return max(pending_tasks, key=lambda x: (x.priority, x.created_at.timestamp()))
