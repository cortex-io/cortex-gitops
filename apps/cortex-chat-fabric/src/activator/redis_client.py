#!/usr/bin/env python3
"""
Redis Client for Chat Fabric

Handles:
- Connection management
- Conversation storage (active + archived)
- Redis Streams for fabric communication
"""
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

import redis.asyncio as redis
import structlog

logger = structlog.get_logger()


class RedisClient:
    """Async Redis client wrapper."""

    def __init__(self, host: str, port: int, password: str = ""):
        self.host = host
        self.port = port
        self.password = password
        self._client: Optional[redis.Redis] = None
        self.connected = False

    async def connect(self):
        """Connect to Redis."""
        try:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password if self.password else None,
                decode_responses=True
            )
            await self._client.ping()
            self.connected = True
            logger.info("redis_connected", host=self.host, port=self.port)
        except Exception as e:
            logger.error("redis_connection_failed", error=str(e))
            self.connected = False

    async def disconnect(self):
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            self.connected = False
            logger.info("redis_disconnected")

    @property
    def client(self) -> redis.Redis:
        if not self._client:
            raise RuntimeError("Redis not connected")
        return self._client

    # Stream operations
    async def xadd(self, stream: str, data: Dict[str, Any], maxlen: int = 10000) -> str:
        """Add message to stream."""
        return await self.client.xadd(stream, data, maxlen=maxlen)

    async def xread(self, streams: Dict[str, str], count: int = 10,
                    block: int = 5000) -> List:
        """Read from streams."""
        return await self.client.xread(streams, count=count, block=block)

    async def xreadgroup(self, group: str, consumer: str, streams: Dict[str, str],
                         count: int = 10, block: int = 5000) -> List:
        """Read from stream as consumer group."""
        try:
            return await self.client.xreadgroup(
                group, consumer, streams, count=count, block=block
            )
        except redis.ResponseError as e:
            if "NOGROUP" in str(e):
                # Create consumer group if it doesn't exist
                for stream in streams.keys():
                    try:
                        await self.client.xgroup_create(stream, group, id="0", mkstream=True)
                    except redis.ResponseError:
                        pass  # Group already exists
                return await self.client.xreadgroup(
                    group, consumer, streams, count=count, block=block
                )
            raise

    async def xack(self, stream: str, group: str, *ids: str):
        """Acknowledge messages."""
        return await self.client.xack(stream, group, *ids)


class ConversationStore:
    """Conversation storage backed by Redis."""

    CONV_PREFIX = "chat:conv:"
    ARCHIVED_PREFIX = "chat:archived:"

    def __init__(self, redis_client: RedisClient):
        self.redis = redis_client

    async def create_conversation(self, conv_id: Optional[str] = None,
                                   title: Optional[str] = None) -> Dict[str, Any]:
        """Create a new conversation."""
        if conv_id is None:
            conv_id = f"conv-{uuid.uuid4().hex[:8]}"

        now = datetime.utcnow().isoformat() + "Z"
        conv = {
            "id": conv_id,
            "title": title or f"Conversation {conv_id}",
            "messages": [],
            "status": "active",
            "created_at": now,
            "updated_at": now
        }

        await self.redis.client.set(
            f"{self.CONV_PREFIX}{conv_id}",
            json.dumps(conv)
        )

        logger.info("conversation_created", conversation_id=conv_id)
        return conv

    async def get_conversation(self, conv_id: str) -> Optional[Dict[str, Any]]:
        """Get a conversation by ID."""
        # Check active first
        data = await self.redis.client.get(f"{self.CONV_PREFIX}{conv_id}")
        if data:
            return json.loads(data)

        # Check archived
        data = await self.redis.client.get(f"{self.ARCHIVED_PREFIX}{conv_id}")
        if data:
            conv = json.loads(data)
            conv["status"] = "archived"
            return conv

        return None

    async def save_conversation(self, conv: Dict[str, Any]):
        """Save a conversation."""
        conv_id = conv["id"]
        conv["updated_at"] = datetime.utcnow().isoformat() + "Z"
        await self.redis.client.set(
            f"{self.CONV_PREFIX}{conv_id}",
            json.dumps(conv)
        )

    async def delete_conversation(self, conv_id: str) -> bool:
        """Delete a conversation permanently."""
        deleted = await self.redis.client.delete(f"{self.CONV_PREFIX}{conv_id}")
        await self.redis.client.delete(f"{self.ARCHIVED_PREFIX}{conv_id}")
        if deleted:
            logger.info("conversation_deleted", conversation_id=conv_id)
        return deleted > 0

    async def archive_conversation(self, conv_id: str) -> bool:
        """Move conversation to archived storage."""
        data = await self.redis.client.get(f"{self.CONV_PREFIX}{conv_id}")
        if not data:
            return False

        conv = json.loads(data)
        conv["status"] = "archived"
        conv["archived_at"] = datetime.utcnow().isoformat() + "Z"

        await self.redis.client.delete(f"{self.CONV_PREFIX}{conv_id}")
        await self.redis.client.set(
            f"{self.ARCHIVED_PREFIX}{conv_id}",
            json.dumps(conv)
        )

        logger.info("conversation_archived", conversation_id=conv_id)
        return True

    async def restore_conversation(self, conv_id: str) -> bool:
        """Restore an archived conversation."""
        data = await self.redis.client.get(f"{self.ARCHIVED_PREFIX}{conv_id}")
        if not data:
            return False

        conv = json.loads(data)
        conv["status"] = "completed"
        conv.pop("archived_at", None)
        conv["updated_at"] = datetime.utcnow().isoformat() + "Z"

        await self.redis.client.delete(f"{self.ARCHIVED_PREFIX}{conv_id}")
        await self.redis.client.set(
            f"{self.CONV_PREFIX}{conv_id}",
            json.dumps(conv)
        )

        logger.info("conversation_restored", conversation_id=conv_id)
        return True

    async def update_status(self, conv_id: str, status: str) -> Optional[Dict[str, Any]]:
        """Update conversation status."""
        conv = await self.get_conversation(conv_id)
        if not conv or conv.get("status") == "archived":
            return None

        conv["status"] = status
        await self.save_conversation(conv)
        return conv

    async def add_message(self, conv_id: str, role: str, content: str):
        """Add a message to a conversation."""
        conv = await self.get_conversation(conv_id)
        if not conv:
            conv = await self.create_conversation(conv_id=conv_id)

        conv["messages"].append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

        await self.save_conversation(conv)

    async def get_messages(self, conv_id: str) -> List[Dict[str, Any]]:
        """Get messages from a conversation."""
        conv = await self.get_conversation(conv_id)
        if not conv:
            return []
        return conv.get("messages", [])

    async def list_conversations(self, status_filter: Optional[str] = None,
                                  include_archived: bool = False) -> List[Dict[str, Any]]:
        """List all conversations."""
        result = []

        # Get active conversations
        async for key in self.redis.client.scan_iter(f"{self.CONV_PREFIX}*"):
            data = await self.redis.client.get(key)
            if data:
                conv = json.loads(data)
                if status_filter and conv.get("status") != status_filter:
                    continue

                last_msg = conv.get("messages", [])[-1] if conv.get("messages") else None
                result.append({
                    "id": conv.get("id"),
                    "title": conv.get("title", f"Conversation {conv.get('id')}"),
                    "status": conv.get("status", "active"),
                    "lastMessage": last_msg.get("content", "No messages")[:100] if last_msg else "No messages",
                    "messageCount": len(conv.get("messages", [])),
                    "created_at": conv.get("created_at"),
                    "updated_at": conv.get("updated_at")
                })

        # Get archived if requested
        if include_archived:
            async for key in self.redis.client.scan_iter(f"{self.ARCHIVED_PREFIX}*"):
                data = await self.redis.client.get(key)
                if data:
                    conv = json.loads(data)
                    last_msg = conv.get("messages", [])[-1] if conv.get("messages") else None
                    result.append({
                        "id": conv.get("id"),
                        "title": conv.get("title", f"Conversation {conv.get('id')}"),
                        "status": "archived",
                        "lastMessage": last_msg.get("content", "No messages")[:100] if last_msg else "No messages",
                        "messageCount": len(conv.get("messages", [])),
                        "created_at": conv.get("created_at"),
                        "updated_at": conv.get("updated_at"),
                        "archived_at": conv.get("archived_at")
                    })

        # Sort by updated_at descending
        result.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return result
