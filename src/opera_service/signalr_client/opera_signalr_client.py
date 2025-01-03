"""Opera SignalR 客户端模块，用于处理与Opera服务器的实时通信。

提供了与Opera服务器建立SignalR连接、处理各种实时事件（如剧本创建、消息接收等）的功能。
支持自动重连、健康检查和各种回调机制。
"""

from typing import Optional, List, Callable, Any, Dict
from uuid import UUID
import json
import asyncio
from datetime import datetime
from dataclasses import dataclass

from pysignalr.client import SignalRClient
from pysignalr.messages import CompletionMessage
from src.core.logger_config import get_logger, get_logger_with_trace_id
from src.crewai_ext.tools.opera_api.staff_invitation_api_tool import StaffInvitationTool

# 获取logger实例
logger = get_logger(__name__, log_file="logs/opera_signalr.log")


@dataclass
class OperaCreatedArgs:
    opera_id: UUID
    parent_id: Optional[UUID]
    name: str
    description: Optional[str]
    database_name: str


@dataclass
class MessageReceivedArgs:
    opera_id: UUID
    receiver_staff_ids: List[UUID]
    index: int
    time: datetime
    stage_index: Optional[int]
    sender_staff_id: Optional[UUID]
    is_narratage: bool
    is_whisper: bool
    text: str
    tags: Optional[str]
    mentioned_staff_ids: Optional[List[UUID]]


class OperaSignalRClient:
    def __init__(self, url: str = "http://opera.nti56.com/signalRService", bot_id: Optional[str] = None):
        self.url = url
        self.client = SignalRClient(self.url)
        self.bot_id = UUID(bot_id) if bot_id else None
        self.snitch_mode: bool = False
        self._connected = False
        self.staff_invitation_tool = StaffInvitationTool()  # 初始化StaffInvitationTool
        # 为每个实例创建一个带trace_id的logger
        self.log = get_logger_with_trace_id()

        # 设置基本回调
        self.client.on_open(self._on_open)
        self.client.on_close(self._on_close)
        self.client.on_error(self._on_error)

        # 注册所有回调方法
        self.client.on("Hello", self._handle_hello)
        self.client.on("OnSystemShutdown", self._handle_system_shutdown)
        self.client.on("OnOperaCreated", self._handle_opera_created)
        self.client.on("OnOperaDeleted", self._handle_opera_deleted)
        self.client.on("OnStaffInvited", self._handle_staff_invited)
        self.client.on("OnStageChanged", self._handle_stage_changed)
        self.client.on("OnMessageReceived", self._handle_message_received)

        # 回调函数字典
        self.callbacks = {
            "on_hello": None,
            "on_system_shutdown": None,
            "on_opera_created": None,
            "on_opera_deleted": None,
            "on_staff_invited": None,
            "on_stage_changed": None,
            "on_message_received": None
        }

        # 添加回调状追踪
        self.callback_stats = {
            name: {"success": 0, "error": 0, "last_execution": None}
            for name in self.callbacks
        }

        # 设置回调超时时间(秒)
        self.callback_timeout = 30
        self._connection_task = None

    async def _on_open(self) -> None:
        self.log.info(
            f"已连接到服务器 [Bot ID: {self.bot_id if self.bot_id else 'Not Set'}]")
        self._connected = True
        # 如果有bot_id，自动设置
        if self.bot_id:
            await self.set_bot_id(self.bot_id)
        if self.snitch_mode:
            await self.set_snitch_mode(True)

    async def _on_close(self) -> None:
        self.log.info(
            f"与服务器断开连接 [Bot ID: {self.bot_id if self.bot_id else 'Not Set'}]")
        self._connected = False

    async def _on_error(self, message: CompletionMessage) -> None:
        self.log.error(f"发生错误: {message.error}")

    async def connect(self):
        """建立SignalR连接"""
        try:
            self.log.debug("开始建立连接...")
            self._connection_task = asyncio.create_task(self.client.run())
            await asyncio.sleep(0.1)  # 给予连接初始化的时间
        except Exception as e:
            self.log.exception(f"连接失败: {str(e)}")
            raise

    async def disconnect(self):
        """安全地断开连接"""
        try:
            if self._connection_task and not self._connection_task.done():
                # 只在任务还在运行时才取消
                self._connection_task.cancel()
                try:
                    await self._connection_task
                except asyncio.CancelledError:
                    pass
            self._connection_task = None

        except Exception as e:
            self.log.exception(f"断开连接时出错: {e}")

    async def set_bot_id(self, bot_id: UUID):
        """设置Bot ID"""
        self.bot_id = bot_id
        await self.client.send("SetBotId", [str(bot_id)])

    async def set_snitch_mode(self, enabled: bool):
        """设置告密模式"""
        self.snitch_mode = enabled
        await self.client.send("SetSnitchMode", [enabled])

    async def send(self, method: str, args: list):
        """发送消息到SignalR服务器

        Args:
            method: 要调用的方法名
            args: 参数列表
        """
        await self.client.send(method, args)

    def set_callback(self, event_name: str, callback: Callable):
        """设置回调函数"""
        if event_name not in self.callbacks:
            raise ValueError(f"未知的事件名称: {event_name}")
        self.callbacks[event_name] = callback

    async def _execute_callback(
        self,
        callback_name: str,
        callback: Callable,
        *args,
        **kwargs
    ) -> None:
        """安全地执行回调函数

        Args:
            callback_name: 回调函数名称
            callback: 回调函数
            args: 位置参数
            kwargs: 关键字参数
        """
        if not callback:
            return

        try:
            # 添加超时控制
            async with asyncio.timeout(self.callback_timeout):
                await callback(*args, **kwargs)

            # 更新统计
            self.callback_stats[callback_name]["success"] += 1
            self.callback_stats[callback_name]["last_execution"] = datetime.now(
            )

        except asyncio.TimeoutError:
            self.log.error(
                f"回调 {callback_name} 执行超时 (>{self.callback_timeout}秒)"
            )
            self.callback_stats[callback_name]["error"] += 1

        except Exception as _:
            self.log.exception(f"回调 {callback_name} 执行出错")
            self.callback_stats[callback_name]["error"] += 1

    # 内部处理方法
    async def _handle_hello(self, *args) -> None:
        if self.callbacks["on_hello"]:
            await self._execute_callback("on_hello", self.callbacks["on_hello"])
        else:
            self.log.debug("收到Hello事件，但未设置处理回调")

    async def _handle_system_shutdown(self, *args) -> None:
        self.log.warning(f"收到系统关闭事件: {args}")
        if self.callbacks["on_system_shutdown"]:
            await self._execute_callback("on_system_shutdown", self.callbacks["on_system_shutdown"])
        else:
            self.log.debug("收到系统关闭事件，但未设置处理回调")

    async def _handle_opera_created(self, args: Dict[str, Any]) -> None:
        self.log.info(f"收到Opera创建事件: {json.dumps(args, ensure_ascii=False)}")
        if self.callbacks["on_opera_created"]:
            opera_args = OperaCreatedArgs(
                opera_id=UUID(args["operaId"]),
                parent_id=UUID(args["parentId"]) if args.get(
                    "parentId") else None,
                name=args["name"],
                description=args.get("description"),
                database_name=args["databaseName"]
            )
            self.log.debug(f"Opera创建详情: ID={opera_args.opera_id}, 名称={opera_args.name}, "
                         f"父ID={opera_args.parent_id}, 数据库={opera_args.database_name}")
            await self.message_processor.handle_opera_created(opera_args)
            await self._execute_callback(
                "on_opera_created",
                self.callbacks["on_opera_created"],
                opera_args
            )
        else:
            self.log.warning("收到Opera创建事件，但未设置处理回调")

    async def _handle_opera_deleted(self, args: Dict[str, Any]) -> None:
        self.log.info(f"收到Opera删除事件: {json.dumps(args, ensure_ascii=False)}")
        if self.callbacks["on_opera_deleted"]:
            opera_id = UUID(args["operaId"])
            self.log.debug(f"Opera删除详情: ID={opera_id}")
            await self._execute_callback("on_opera_deleted", self.callbacks["on_opera_deleted"], opera_id)
        else:
            self.log.warning("收到Opera删除事件，但未设置处理回调")

    async def _handle_staff_invited(self, args: Dict[str, Any]) -> None:
        self.log.info(f"收到Staff邀请事件: {json.dumps(args, ensure_ascii=False)}")
        try:
            # 准备接受邀请所需的数据
            opera_id = UUID(args["operaId"])
            invitation_id = UUID(args["invitationId"])
            roles = args["roles"]

            # 构造接受邀请的数据
            acceptance_data = {
                "name": f"{self.roles}" if self.roles else "AutoBot",
                "parameter": args["parameter"],
                "is_on_stage": True,
                "tags": args["tags"],
                "roles": args["roles"],
                "permissions": args["permissions"]
            }

            # 使用StaffInvitationTool接受邀请
            result = self.staff_invitation_tool.run(
                action="accept",
                opera_id=opera_id,
                invitation_id=invitation_id,
                data=acceptance_data
            )
            self.log.info(f"自动接受邀请: {result}")

            # 继续执行原有的回调逻辑
            if self.callbacks["on_staff_invited"]:
                invite_data = {
                    "opera_id": opera_id,
                    "invitation_id": invitation_id,
                    "parameter": json.loads(args["parameter"]),
                    "tags": args["tags"],
                    "roles": args["roles"],
                    "permissions": args["permissions"]
                }
                await self._execute_callback("on_staff_invited", self.callbacks["on_staff_invited"], invite_data)
        except Exception as e:
            self.log.error(f"自动接受邀请失败: {str(e)}")

    async def _handle_stage_changed(self, args: Dict[str, Any]) -> None:
        self.log.info(f"收到Stage变更事件: {json.dumps(args, ensure_ascii=False)}")
        if self.callbacks["on_stage_changed"]:
            stage_data = {
                "opera_id": UUID(args["operaId"]),
                "stage_index": args["stageIndex"],
                "stage_name": args["stageName"]
            }
            self.log.debug(f"Stage变更详情: Opera ID={stage_data['opera_id']}, "
                         f"阶段索引={stage_data['stage_index']}, "
                         f"阶段名称={stage_data['stage_name']}")
            await self._execute_callback("on_stage_changed", self.callbacks["on_stage_changed"], stage_data)
        else:
            self.log.warning("收到Stage变更事件，但未设置处理回调")

    async def _handle_message_received(self, args: Dict[str, Any]) -> None:
        """处理接收到的消息"""
        self.log.info(f"收到消息: {json.dumps(args[0], ensure_ascii=False)}")
        if self.callbacks["on_message_received"]:
            message_args = MessageReceivedArgs(
                opera_id=UUID(args[0]["operaId"]),
                receiver_staff_ids=[UUID(id_str)
                                    for id_str in args[0]["receiverStaffIds"]],
                index=args[0]["index"],
                time=datetime.fromisoformat(args[0]["time"]),
                stage_index=args[0].get("stageIndex"),
                sender_staff_id=UUID(args[0]["senderStaffId"]) if args[0].get(
                    "senderStaffId") else None,
                is_narratage=args[0]["isNarratage"],
                is_whisper=args[0]["isWhisper"],
                text=args[0]["text"],
                tags=args[0].get("tags"),
                mentioned_staff_ids=[UUID(id_str) for id_str in args[0].get(
                    "mentionedStaffIds", [])] if args[0].get("mentionedStaffIds") else None
            )
            await self._execute_callback(
                "on_message_received",
                self.callbacks["on_message_received"],
                message_args
            )
        else:
            self.log.warning("收到消息，但未设置处理回调")

    # 在OperaSignalRClient类中添加重试机制
    async def connect_with_retry(self, max_retries=3, retry_delay=5):
        for attempt in range(max_retries):
            try:
                await self.connect()
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                self.log.error(f"连接失败，{retry_delay}秒后重试: {str(e)}")
                await asyncio.sleep(retry_delay)

    # 添加心跳检测
    async def check_health(self):
        while True:
            if not self.is_connected():
                self.log.warning("连接已断开，尝试重连")
                await self.connect_with_retry()
            await asyncio.sleep(30)  # 每30秒检查一次

    # 添加获取回调统计信息的方法
    def get_callback_stats(self) -> Dict[str, Dict]:
        """获取回调函数执行统计信息"""
        return self.callback_stats

    def print_callback_stats(self) -> None:
        """打印所有回调函数的执行统计信息"""
        self.log.info("回调函数执行统计:")
        for name, stats in self.callback_stats.items():
            success_rate = 0
            total = stats["success"] + stats["error"]
            if total > 0:
                success_rate = (stats["success"] / total) * 100

            last_exec = stats["last_execution"].strftime(
                "%Y-%m-%d %H:%M:%S") if stats["last_execution"] else "从未执行"

            self.log.info(
                f"回调 {name}:\n"
                f"  成功次数: {stats['success']}\n"
                f"  失败次数: {stats['error']}\n"
                f"  成功率: {success_rate:.2f}%\n"
                f"  最后执行: {last_exec}"
            )

    def get_callback_stats_summary(self) -> Dict[str, Any]:
        """获取回调统计的摘要信息"""
        summary = {
            "total_success": 0,
            "total_error": 0,
            "callback_details": {}
        }

        for name, stats in self.callback_stats.items():
            summary["total_success"] += stats["success"]
            summary["total_error"] += stats["error"]
            summary["callback_details"][name] = {
                "success_count": stats["success"],
                "error_count": stats["error"],
                "success_rate": 0 if (stats["success"] + stats["error"]) == 0 else
                (stats["success"] / (stats["success"] + stats["error"])) * 100,
                "last_execution": stats["last_execution"]
            }

        return summary

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected
