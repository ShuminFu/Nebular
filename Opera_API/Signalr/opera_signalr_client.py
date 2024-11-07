from pysignalr.client import SignalRClient
from typing import Optional, List, Callable, Any, Dict
from uuid import UUID
import json
import asyncio
from loguru import logger
from datetime import datetime
from dataclasses import dataclass
from pysignalr.messages import CompletionMessage
import sys

# 配置日志
logger.configure(
    handlers=[
        {
            "sink": sys.stdout,
            "format": "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            "level": "INFO",
        },
        {
            "sink": "logs/opera_signalr.log",
            "rotation": "500 MB",
            "retention": "10 days",
            "compression": "zip",
            "format": "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            "level": "DEBUG",
        }
    ]
)


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
        self.snitch_mode: bool = True

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

        # 添加回调状态追踪
        self.callback_stats = {
            name: {"success": 0, "error": 0, "last_execution": None}
            for name in self.callbacks.keys()
        }
        
        # 设置回调超时时间(秒)
        self.callback_timeout = 30

    async def _on_open(self) -> None:
        logger.info("已连接到服务器")
        # 重新设置之前的状态
        if self.bot_id:
            await self.set_bot_id(self.bot_id)
        if self.snitch_mode:
            await self.set_snitch_mode(True)

    async def _on_close(self) -> None:
        logger.info("与服务器断开连接")

    async def _on_error(self, message: CompletionMessage) -> None:
        logger.error(f"发生错误: {message.error}")

    async def connect(self):
        """建立SignalR连接"""
        try:
            logger.debug("开始建立连接...")
            await self.client.run()
        except Exception as e:
            logger.exception(f"连接失败: {str(e)}")
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
            self.callback_stats[callback_name]["last_execution"] = datetime.now()
            
        except asyncio.TimeoutError:
            logger.error(
                f"回调 {callback_name} 执行超时 (>{self.callback_timeout}秒)"
            )
            self.callback_stats[callback_name]["error"] += 1
            
        except Exception as e:
            logger.exception(f"回调 {callback_name} 执行出错")
            self.callback_stats[callback_name]["error"] += 1

    # 内部处理方法
    async def _handle_hello(self, *args) -> None:
        logger.info(f"Hello!")
        if self.callbacks["on_hello"]:
            await self._execute_callback("on_hello", self.callbacks["on_hello"])
        else:
            logger.debug("收到Hello事件，但未设置处理回调")

    async def _handle_system_shutdown(self, *args) -> None:
        logger.warning(f"收到系统关闭事件: {args}")
        if self.callbacks["on_system_shutdown"]:
            await self._execute_callback("on_system_shutdown", self.callbacks["on_system_shutdown"])
        else:
            logger.debug("收到系统关闭事件，但未设置处理回调")

    async def _handle_opera_created(self, args: Dict[str, Any]) -> None:
        logger.info(f"收到Opera创建事件: {json.dumps(args, ensure_ascii=False)}")
        if self.callbacks["on_opera_created"]:
            opera_args = OperaCreatedArgs(
                opera_id=UUID(args["operaId"]),
                parent_id=UUID(args["parentId"]) if args.get("parentId") else None,
                name=args["name"],
                description=args.get("description"),
                database_name=args["databaseName"]
            )
            logger.debug(f"Opera创建详情: ID={opera_args.opera_id}, 名称={opera_args.name}, "
                        f"父ID={opera_args.parent_id}, 数据库={opera_args.database_name}")
            await self._execute_callback(
                "on_opera_created",
                self.callbacks["on_opera_created"], 
                opera_args
            )
        else:
            logger.warning("收到Opera创建事件，但未设置处理回调")

    async def _handle_opera_deleted(self, args: Dict[str, Any]) -> None:
        logger.info(f"收到Opera删除事件: {json.dumps(args, ensure_ascii=False)}")
        if self.callbacks["on_opera_deleted"]:
            opera_id = UUID(args["operaId"])
            logger.debug(f"Opera删除详情: ID={opera_id}")
            await self._execute_callback("on_opera_deleted", self.callbacks["on_opera_deleted"], opera_id)
        else:
            logger.warning("收到Opera删除事件，但未设置处理回调")

    async def _handle_staff_invited(self, args: Dict[str, Any]) -> None:
        logger.info(f"收到Staff邀请事件: {json.dumps(args, ensure_ascii=False)}")
        if self.callbacks["on_staff_invited"]:
            invite_data = {
                "opera_id": UUID(args["operaId"]),
                "invitation_id": UUID(args["invitationId"]),
                "parameter": json.loads(args["parameter"]),
                "tags": args["tags"],
                "roles": args["roles"],
                "permissions": args["permissions"]
            }
            logger.debug(f"Staff邀请详情: Opera ID={invite_data['opera_id']}, "
                        f"邀请ID={invite_data['invitation_id']}, "
                        f"角色={invite_data['roles']}, "
                        f"权限={invite_data['permissions']}")
            await self._execute_callback("on_staff_invited", self.callbacks["on_staff_invited"], invite_data)
        else:
            logger.warning("收到Staff邀请事件，但未设置处理回调")

    async def _handle_stage_changed(self, args: Dict[str, Any]) -> None:
        logger.info(f"收到Stage变更事件: {json.dumps(args, ensure_ascii=False)}")
        if self.callbacks["on_stage_changed"]:
            stage_data = {
                "opera_id": UUID(args["operaId"]),
                "stage_index": args["stageIndex"],
                "stage_name": args["stageName"]
            }
            logger.debug(f"Stage变更详情: Opera ID={stage_data['opera_id']}, "
                        f"阶段索引={stage_data['stage_index']}, "
                        f"阶段名称={stage_data['stage_name']}")
            await self._execute_callback("on_stage_changed", self.callbacks["on_stage_changed"], stage_data)
        else:
            logger.warning("收到Stage变更事件，但未设置处理回调")

    async def _handle_message_received(self, args: Dict[str, Any]) -> None:
        logger.info(f"收到消息事件: {json.dumps(args, ensure_ascii=False)}")
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
                mentioned_staff_ids=[UUID(x) for x in args["MentionedStaffIds"]] if args.get("MentionedStaffIds") else None
            )
            logger.debug(f"消息详情: Opera ID={msg_args.opera_id}, "
                        f"发送者ID={msg_args.sender_staff_id}, "
                        f"接收者数量={len(msg_args.receiver_staff_ids)}, "
                        f"消息内容={msg_args.text[:100]}...")  # 只显示前100个字符
            await self._execute_callback("on_message_received", self.callbacks["on_message_received"], msg_args)
        else:
            logger.warning("收到消息事件，但未设置处理回调")

    # 在OperaSignalRClient类中添加重试机制
    async def connect_with_retry(self, max_retries=3, retry_delay=5):
        for attempt in range(max_retries):
            try:
                await self.connect()
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.error(f"连接失败，{retry_delay}秒后重试: {str(e)}")
                await asyncio.sleep(retry_delay)

    # 添加心跳检测
    async def check_health(self):
        while True:
            if not self.client.connection.connected:
                logger.warning("连接已断开，尝试重连")
                await self.connect_with_retry()
            await asyncio.sleep(30)  # 每30秒检查一次

    # 添加获取回调统计信息的方法
    def get_callback_stats(self) -> Dict[str, Dict]:
        """获取回调函数执行统计信息"""
        return self.callback_stats

    def print_callback_stats(self) -> None:
        """打印所有回调函数的执行统计信息"""
        logger.info("回调函数执行统计:")
        for name, stats in self.callback_stats.items():
            success_rate = 0
            total = stats["success"] + stats["error"]
            if total > 0:
                success_rate = (stats["success"] / total) * 100
                
            last_exec = stats["last_execution"].strftime("%Y-%m-%d %H:%M:%S") if stats["last_execution"] else "从未执行"
            
            logger.info(
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