from pysignalr.client import SignalRClient
from typing import Optional, List, Callable, Any, Dict
from uuid import UUID
import json
import asyncio
import logging
from datetime import datetime
from dataclasses import dataclass
from pysignalr.messages import CompletionMessage


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
    def __init__(self, url: str = "http://opera.nti56.com/signalRService"):
        self.url = url
        self.client = SignalRClient(self.url)
        self.bot_id: Optional[UUID] = None
        self.snitch_mode: bool = False
        self.logger = logging.getLogger("OperaSignalRClient")

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

    async def _on_open(self) -> None:
        self.logger.info("已连接到服务器")
        # 重新设置之前的状态
        if self.bot_id:
            await self.set_bot_id(self.bot_id)
        if self.snitch_mode:
            await self.set_snitch_mode(True)

    async def _on_close(self) -> None:
        self.logger.info("与服务器断开连接")

    async def _on_error(self, message: CompletionMessage) -> None:
        self.logger.error(f"发生错误: {message.error}")

    async def connect(self):
        """建立SignalR连接"""
        try:
            await self.client.run()
        except Exception as e:
            self.logger.error(f"连接失败: {str(e)}")
            raise

    async def set_bot_id(self, bot_id: UUID):
        """设置Bot ID"""
        self.bot_id = bot_id
        await self.client.send("SetBotId", [str(bot_id)])

    async def set_snitch_mode(self, enabled: bool):
        """设置告密模式"""
        self.snitch_mode = enabled
        await self.client.send("SetSnitchMode", [enabled])

    def set_callback(self, event_name: str, callback: Callable):
        """设置回调函数"""
        if event_name not in self.callbacks:
            raise ValueError(f"未知的事件名称: {event_name}")
        self.callbacks[event_name] = callback

    # 内部处理方法
    async def _handle_hello(self, *args) -> None:
        if self.callbacks["on_hello"]:
            await self.callbacks["on_hello"]()

    async def _handle_system_shutdown(self, *args) -> None:
        if self.callbacks["on_system_shutdown"]:
            await self.callbacks["on_system_shutdown"]()

    async def _handle_opera_created(self, args: Dict[str, Any]) -> None:
        if self.callbacks["on_opera_created"]:
            opera_args = OperaCreatedArgs(
                opera_id=UUID(args["operaId"]),
                parent_id=UUID(args["parentId"]) if args.get("parentId") else None,
                name=args["name"],
                description=args.get("description"),
                database_name=args["databaseName"]
            )
            await self.callbacks["on_opera_created"](opera_args)

    async def _handle_opera_deleted(self, args: Dict[str, Any]) -> None:
        if self.callbacks["on_opera_deleted"]:
            await self.callbacks["on_opera_deleted"](UUID(args["operaId"]))

    async def _handle_staff_invited(self, args: Dict[str, Any]) -> None:
        if self.callbacks["on_staff_invited"]:
            await self.callbacks["on_staff_invited"]({
                "opera_id": UUID(args["operaId"]),
                "invitation_id": UUID(args["invitationId"]),
                "parameter": json.loads(args["parameter"]),
                "tags": args["tags"],
                "roles": args["roles"],
                "permissions": args["permissions"]
            })

    async def _handle_stage_changed(self, args: Dict[str, Any]) -> None:
        if self.callbacks["on_stage_changed"]:
            await self.callbacks["on_stage_changed"]({
                "opera_id": UUID(args["operaId"]),
                "stage_index": args["stageIndex"],
                "stage_name": args["stageName"]
            })

    async def _handle_message_received(self, args: Dict[str, Any]) -> None:
        if self.callbacks["on_message_received"]:
            msg_args = MessageReceivedArgs(
                opera_id=UUID(args["OperaId"]),
                receiver_staff_ids=[UUID(x) for x in args["ReceiverStaffIds"]],
                index=args["Index"],
                time=datetime.fromisoformat(args["Time"]),
                stage_index=args.get("StageIndex"),
                sender_staff_id=UUID(args["SenderStaffId"]) if args.get("SenderStaffId") else None,
                is_narratage=args["IsNarratage"],
                is_whisper=args["IsWhisper"],
                text=args["Text"],
                tags=args.get("Tags"),
                mentioned_staff_ids=[UUID(x) for x in args["MentionedStaffIds"]] if args.get(
                    "MentionedStaffIds") else None
            )
            await self.callbacks["on_message_received"](msg_args)