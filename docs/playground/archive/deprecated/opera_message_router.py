from typing import Dict, Set, Optional
from uuid import UUID
from dataclasses import dataclass, field
import asyncio
from loguru import logger


@dataclass
class Identity:
    bot_id: Optional[UUID] = None
    staff_ids: Set[UUID] = field(default_factory=set)  # 一个Bot可能有多个Staff身份


@dataclass
class SubscriptionInfo:
    identity: Identity
    opera_ids: Set[UUID]
    queue: asyncio.Queue


class MessageRouter:
    def __init__(self):
        self.subscriptions: Dict[UUID, SubscriptionInfo] = {}
        self._lock = asyncio.Lock()
        self.stats = {
            'messages_routed': 0,
            'routing_errors': 0,
            'active_subscriptions': 0
        }

    async def subscribe(self,
                        subscriber_id: UUID,
                        bot_id: Optional[UUID] = None,
                        staff_ids: Optional[Set[UUID]] = None,
                        opera_ids: Optional[Set[UUID]] = None) -> asyncio.Queue:
        """订阅消息

        Args:
            subscriber_id: 订阅者ID
            bot_id: Bot ID
            staff_ids: Staff ID集合
            opera_ids: src ID集合
        """
        async with self._lock:
            queue = asyncio.Queue()
            self.subscriptions[subscriber_id] = SubscriptionInfo(
                identity=Identity(
                    bot_id=bot_id,
                    staff_ids=staff_ids or set()
                ),
                opera_ids=opera_ids or set(),
                queue=queue
            )
            return queue

    async def update_subscription(self,
                                  subscriber_id: UUID,
                                  add_staff_id: Optional[UUID] = None,
                                  remove_staff_id: Optional[UUID] = None,
                                  add_opera_id: Optional[UUID] = None,
                                  remove_opera_id: Optional[UUID] = None):
        """更新订阅信息"""
        async with self._lock:
            if subscriber_id not in self.subscriptions:
                return

            sub_info = self.subscriptions[subscriber_id]

            if add_staff_id:
                sub_info.identity.staff_ids.add(add_staff_id)
            if remove_staff_id:
                sub_info.identity.staff_ids.discard(remove_staff_id)
            if add_opera_id:
                sub_info.opera_ids.add(add_opera_id)
            if remove_opera_id:
                sub_info.opera_ids.discard(remove_opera_id)

    async def route_message(self, message: dict):
        """路由消息到相关订阅者"""
        try:
            async with self._lock:
                routed_count = 0
                for subscriber_id, sub_info in self.subscriptions.items():
                    if await self._should_route_message(message, sub_info):
                        try:
                            await sub_info.queue.put(message)
                            routed_count += 1
                        except Exception as e:
                            logger.error(
                                f"消息投递失败 (subscriber_id={subscriber_id}): {e}")
                            self.stats['routing_errors'] += 1

                self.stats['messages_routed'] += routed_count
                self.stats['active_subscriptions'] = len(self.subscriptions)

        except Exception as e:
            self.stats['routing_errors'] += 1
            logger.exception(f"消息路由过程失败: {e}")

    async def _should_route_message(self, message: dict, sub_info: SubscriptionInfo) -> bool:
        """检查消息是否应该路由到指定订阅者"""
        target_bot_id = message.get('bot_id')
        target_staff_id = message.get('staff_id')
        opera_id = message.get('opera_id')

        # 检查是否匹配Bot ID
        if target_bot_id and sub_info.identity.bot_id == target_bot_id:
            return True

        # 检查是否匹配Staff ID
        if target_staff_id and target_staff_id in sub_info.identity.staff_ids:
            return True

        # 检查是否匹配Opera ID
        if opera_id and opera_id in sub_info.opera_ids:
            return True

        return False
