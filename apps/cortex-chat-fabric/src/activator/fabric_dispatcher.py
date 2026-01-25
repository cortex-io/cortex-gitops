#!/usr/bin/env python3
"""
Fabric Dispatcher - Routes requests to domain-specific fabrics via Redis Streams

Manages communication with:
- UniFi Fabric (network operations)
- Infrastructure Fabric (Kubernetes, Proxmox)
- Security Fabric (Sandfly, vulnerability scanning)
- Future fabrics...
"""
import json
import uuid
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List

import yaml
import structlog

from redis_client import RedisClient

logger = structlog.get_logger()


class FabricDispatcher:
    """
    Dispatches requests to domain fabrics via Redis Streams.

    Each fabric has:
    - A task stream (where we send requests)
    - Capabilities (what queries it can handle)
    - Health status
    """

    def __init__(self, redis_client: RedisClient):
        self.redis = redis_client
        self.fabrics: Dict[str, Dict[str, Any]] = {}
        self.result_stream = "cortex.results"
        self.consumer_group = "chat-activator"
        self.consumer_name = f"chat-{uuid.uuid4().hex[:8]}"

    async def load_fabric_config(self, config_path: str):
        """Load fabric configuration from YAML file."""
        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)

            self.fabrics = config.get("fabrics", {})
            logger.info("fabrics_loaded", count=len(self.fabrics))

            # Ensure result stream consumer group exists
            try:
                await self.redis.client.xgroup_create(
                    self.result_stream,
                    self.consumer_group,
                    id="0",
                    mkstream=True
                )
            except Exception:
                pass  # Group already exists

        except FileNotFoundError:
            logger.warning("fabric_config_not_found", path=config_path)
            # Use defaults
            self.fabrics = {
                "unifi": {
                    "stream": "cortex.network.tasks",
                    "capabilities": ["network", "wifi", "unifi", "clients", "devices"]
                },
                "infrastructure": {
                    "stream": "cortex.infra.tasks",
                    "capabilities": ["kubernetes", "pods", "deployments", "proxmox", "vm"]
                },
                "security": {
                    "stream": "cortex.security.tasks",
                    "capabilities": ["security", "sandfly", "vulnerability", "scan"]
                }
            }

    def has_fabric(self, fabric_name: str) -> bool:
        """Check if a fabric is registered."""
        return fabric_name in self.fabrics

    def get_fabric_for_query(self, query: str) -> Optional[str]:
        """Determine which fabric should handle a query based on keywords."""
        query_lower = query.lower()

        for fabric_name, fabric_info in self.fabrics.items():
            capabilities = fabric_info.get("capabilities", [])
            for capability in capabilities:
                if capability.lower() in query_lower:
                    return fabric_name

        return None

    async def dispatch(self, fabric: str, query: str,
                       context: Optional[Dict[str, Any]] = None,
                       timeout: float = 30.0) -> Dict[str, Any]:
        """
        Dispatch a query to a fabric and wait for response.

        Args:
            fabric: Name of the target fabric
            query: The user's query
            context: Additional context (conversation history, etc.)
            timeout: How long to wait for response (seconds)

        Returns:
            Response from the fabric
        """
        if fabric not in self.fabrics:
            return {"success": False, "error": f"Unknown fabric: {fabric}"}

        fabric_info = self.fabrics[fabric]
        task_stream = fabric_info.get("stream")

        if not task_stream:
            return {"success": False, "error": f"No stream configured for fabric: {fabric}"}

        # Create task ID for correlation
        task_id = f"task-{uuid.uuid4().hex[:12]}"

        # Build task message
        task = {
            "task_id": task_id,
            "query": query,
            "context": json.dumps(context or {}),
            "source": "chat-activator",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        logger.info("dispatching_to_fabric",
                    fabric=fabric,
                    task_id=task_id,
                    stream=task_stream)

        # Send to fabric's task stream
        await self.redis.xadd(task_stream, task)

        # Wait for response on result stream
        try:
            result = await self._wait_for_result(task_id, timeout)
            return result
        except asyncio.TimeoutError:
            logger.warning("fabric_response_timeout",
                           fabric=fabric,
                           task_id=task_id,
                           timeout=timeout)
            return {"success": False, "error": "Fabric response timeout"}

    async def _wait_for_result(self, task_id: str, timeout: float) -> Dict[str, Any]:
        """Wait for a result message with matching task_id."""
        deadline = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < deadline:
            remaining = deadline - asyncio.get_event_loop().time()
            block_ms = min(int(remaining * 1000), 1000)

            if block_ms <= 0:
                raise asyncio.TimeoutError()

            messages = await self.redis.xreadgroup(
                group=self.consumer_group,
                consumer=self.consumer_name,
                streams={self.result_stream: ">"},
                count=10,
                block=block_ms
            )

            for stream_name, stream_messages in messages:
                for msg_id, msg_data in stream_messages:
                    # Check if this is our result
                    if msg_data.get("task_id") == task_id:
                        # Acknowledge the message
                        await self.redis.xack(
                            self.result_stream,
                            self.consumer_group,
                            msg_id
                        )

                        # Parse response
                        return {
                            "success": msg_data.get("success", "true").lower() == "true",
                            "response": msg_data.get("response", ""),
                            "tool_calls": int(msg_data.get("tool_calls", "0")),
                            "fabric": msg_data.get("fabric", ""),
                            "execution_time_ms": int(msg_data.get("execution_time_ms", "0"))
                        }
                    else:
                        # Not our message, acknowledge anyway to not block
                        # (In production, might want different handling)
                        await self.redis.xack(
                            self.result_stream,
                            self.consumer_group,
                            msg_id
                        )

        raise asyncio.TimeoutError()

    async def check_health(self, fabric: str) -> bool:
        """Check if a fabric is healthy by looking for recent heartbeats."""
        if fabric not in self.fabrics:
            return False

        try:
            # Check for heartbeat in agent registry
            heartbeat_key = f"cortex:agent:{fabric}:heartbeat"
            heartbeat = await self.redis.client.get(heartbeat_key)

            if heartbeat:
                # Check if heartbeat is recent (within 60 seconds)
                try:
                    hb_time = datetime.fromisoformat(heartbeat.replace("Z", "+00:00"))
                    now = datetime.utcnow()
                    age = (now - hb_time.replace(tzinfo=None)).total_seconds()
                    return age < 60
                except Exception:
                    return False

            return False
        except Exception as e:
            logger.error("fabric_health_check_error", fabric=fabric, error=str(e))
            return False

    async def list_active_fabrics(self) -> List[Dict[str, Any]]:
        """List all active fabrics with their health status."""
        result = []
        for fabric_name, fabric_info in self.fabrics.items():
            is_healthy = await self.check_health(fabric_name)
            result.append({
                "name": fabric_name,
                "stream": fabric_info.get("stream"),
                "capabilities": fabric_info.get("capabilities", []),
                "healthy": is_healthy
            })
        return result
