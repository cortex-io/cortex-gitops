#!/usr/bin/env python3
"""
Security Fabric Activator

Handles Sandfly security operations via MCP server.
Consumes tasks from Redis Streams and publishes results back.
"""
import asyncio
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, Dict, Any, List

import yaml
import httpx
import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import redis.asyncio as redis

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logger = structlog.get_logger()

# Configuration
FABRIC_NAME = os.getenv("FABRIC_NAME", "security")
REDIS_HOST = os.getenv("REDIS_HOST", "redis.cortex-system.svc.cluster.local")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
TASK_STREAM = os.getenv("TASK_STREAM", "cortex.security.tasks")
RESULT_STREAM = os.getenv("RESULT_STREAM", "cortex.results")
CONSUMER_GROUP = os.getenv("CONSUMER_GROUP", "security-activator")
AGENT_ID = f"{FABRIC_NAME}-{uuid.uuid4().hex[:8]}"

# Global state
redis_client: Optional[redis.Redis] = None
mcp_servers: Dict[str, str] = {}
mcp_tools: List[Dict[str, Any]] = []
tool_to_server: Dict[str, Dict[str, str]] = {}
running = False


class QueryRequest(BaseModel):
    query: str
    context: Optional[dict] = None


class QueryResponse(BaseModel):
    success: bool
    response: str
    tool_calls: int = 0
    latency_ms: int = 0


async def load_mcp_config():
    """Load MCP server configuration."""
    global mcp_servers
    try:
        with open("/config/mcp-servers.yaml", "r") as f:
            config = yaml.safe_load(f)
        for server in config.get("servers", []):
            mcp_servers[server["name"]] = server["url"]
        logger.info("mcp_config_loaded", servers=list(mcp_servers.keys()))
    except FileNotFoundError:
        logger.warning("mcp_config_not_found")
        mcp_servers = {
            "sandfly-mcp": "http://sandfly-mcp-server.cortex-system.svc.cluster.local:3000",
        }


async def discover_tools():
    """Discover available tools from MCP servers."""
    global mcp_tools, tool_to_server
    mcp_tools = []
    tool_to_server = {}

    async with httpx.AsyncClient(timeout=10.0) as client:
        for server_name, server_url in mcp_servers.items():
            try:
                response = await client.post(
                    server_url,
                    json={"jsonrpc": "2.0", "method": "tools/list", "id": 1}
                )
                if response.status_code == 200:
                    data = response.json()
                    tools = data.get("result", {}).get("tools", [])
                    for tool in tools:
                        tool_name = tool.get("name")
                        prefixed_name = f"{server_name}__{tool_name}"
                        tool_to_server[prefixed_name] = {
                            "server": server_name,
                            "url": server_url,
                            "original_name": tool_name
                        }
                        mcp_tools.append({
                            "name": prefixed_name,
                            "description": f"[{server_name}] {tool.get('description', '')}",
                            "input_schema": tool.get("inputSchema", {})
                        })
                    logger.info("mcp_tools_discovered", server=server_name, count=len(tools))
            except Exception as e:
                logger.error("mcp_discovery_error", server=server_name, error=str(e))

    logger.info("mcp_discovery_complete", total_tools=len(mcp_tools))


async def call_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Execute a tool on its MCP server."""
    if tool_name not in tool_to_server:
        return {"error": f"Unknown tool: {tool_name}"}

    tool_info = tool_to_server[tool_name]
    server_url = tool_info["url"]
    original_name = tool_info["original_name"]

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                server_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": original_name, "arguments": arguments},
                    "id": 1
                }
            )
            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    return {"error": data["error"]}
                result = data.get("result", {})
                if isinstance(result, dict) and "content" in result:
                    content = result["content"]
                    if isinstance(content, list) and len(content) > 0:
                        return content[0].get("text", str(content))
                return result
            else:
                return {"error": f"MCP server returned {response.status_code}"}
        except httpx.TimeoutException:
            return {"error": "MCP tool call timed out"}
        except Exception as e:
            return {"error": str(e)}


async def process_query(query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Process a security query using Sandfly MCP tools."""
    start = time.time()
    tool_calls = 0
    query_lower = query.lower()

    # Security-specific keyword routing
    if "scan" in query_lower or "result" in query_lower:
        result = await call_tool("sandfly-mcp__sandfly_get_results", {"limit": 20})
        tool_calls = 1
    elif "host" in query_lower:
        if "list" in query_lower or "show" in query_lower:
            result = await call_tool("sandfly-mcp__sandfly_list_hosts", {})
            tool_calls = 1
        else:
            result = await call_tool("sandfly-mcp__sandfly_list_hosts", {})
            tool_calls = 1
    elif "alert" in query_lower or "threat" in query_lower:
        result = await call_tool("sandfly-mcp__sandfly_get_alerts", {"severity": "high"})
        tool_calls = 1
    elif "vulnerability" in query_lower or "vuln" in query_lower:
        result = await call_tool("sandfly-mcp__sandfly_get_vulnerabilities", {})
        tool_calls = 1
    elif "status" in query_lower or "overview" in query_lower:
        result = await call_tool("sandfly-mcp__sandfly_get_status", {})
        tool_calls = 1
    else:
        # Default: show security overview
        result = {
            "message": f"Security fabric ready. Available tools: {len(mcp_tools)}",
            "capabilities": [
                "Get scan results",
                "List hosts",
                "Get alerts by severity",
                "Check vulnerabilities",
                "Security status overview"
            ]
        }

    latency_ms = int((time.time() - start) * 1000)

    if isinstance(result, dict) and "error" in result:
        return {
            "success": False,
            "response": result["error"],
            "tool_calls": tool_calls,
            "latency_ms": latency_ms
        }

    response_text = result if isinstance(result, str) else json.dumps(result, indent=2)
    return {
        "success": True,
        "response": response_text,
        "tool_calls": tool_calls,
        "latency_ms": latency_ms
    }


async def consume_tasks():
    """Consume tasks from Redis Streams."""
    global running
    consumer_name = f"{AGENT_ID}-consumer"

    # Create consumer group
    try:
        await redis_client.xgroup_create(TASK_STREAM, CONSUMER_GROUP, id="$", mkstream=True)
    except redis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise

    logger.info("task_consumer_started", stream=TASK_STREAM, group=CONSUMER_GROUP)

    while running:
        try:
            result = await redis_client.xreadgroup(
                CONSUMER_GROUP, consumer_name,
                {TASK_STREAM: ">"},
                count=10, block=5000
            )

            if not result:
                continue

            for stream_name, messages in result:
                for message_id, data in messages:
                    msg_id = message_id.decode() if isinstance(message_id, bytes) else message_id

                    # Decode message data
                    decoded = {
                        k.decode() if isinstance(k, bytes) else k:
                        v.decode() if isinstance(v, bytes) else v
                        for k, v in data.items()
                    }

                    task_id = decoded.get("task_id", msg_id)
                    query = decoded.get("query", "")
                    context_str = decoded.get("context", "{}")

                    try:
                        context = json.loads(context_str)
                    except (json.JSONDecodeError, TypeError):
                        context = {}

                    logger.info("task_received", task_id=task_id, query=query[:50])

                    # Process query
                    result = await process_query(query, context)

                    # Publish result
                    result_data = {
                        "task_id": task_id,
                        "success": str(result["success"]).lower(),
                        "response": result["response"],
                        "fabric": FABRIC_NAME,
                        "tool_calls": str(result["tool_calls"]),
                        "execution_time_ms": str(result["latency_ms"]),
                        "sender": AGENT_ID,
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }

                    await redis_client.xadd(RESULT_STREAM, result_data, maxlen=10000)
                    await redis_client.xack(TASK_STREAM, CONSUMER_GROUP, msg_id)

                    logger.info("task_completed", task_id=task_id, success=result["success"])

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("task_consumer_error", error=str(e))
            await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global redis_client, running

    logger.info("security_activator_starting", fabric=FABRIC_NAME)

    # Connect to Redis
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD if REDIS_PASSWORD else None,
        decode_responses=False
    )
    await redis_client.ping()
    logger.info("redis_connected", host=REDIS_HOST)

    # Load MCP config and discover tools
    await load_mcp_config()
    await discover_tools()

    # Start task consumer
    running = True
    consumer_task = asyncio.create_task(consume_tasks())

    logger.info("security_activator_ready", tools=len(mcp_tools))

    yield

    # Shutdown
    logger.info("security_activator_stopping")
    running = False
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    await redis_client.close()


app = FastAPI(
    title="Security Fabric Activator",
    description="Sandfly security operations via MCP",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health():
    """Health check."""
    redis_ok = redis_client is not None
    return {
        "status": "healthy" if redis_ok else "degraded",
        "service": "security-activator",
        "fabric": FABRIC_NAME,
        "redis_connected": redis_ok,
        "mcp_tools": len(mcp_tools)
    }


@app.get("/ready")
async def ready():
    """Readiness check."""
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis not connected")
    return {"status": "ready"}


@app.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest):
    """HTTP endpoint for direct queries."""
    result = await process_query(request.query, request.context)
    return QueryResponse(**result)


@app.get("/tools")
async def list_tools():
    """List available MCP tools."""
    return {
        "tools": [{"name": t["name"], "description": t.get("description", "")} for t in mcp_tools],
        "count": len(mcp_tools),
        "servers": list(mcp_servers.keys())
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
