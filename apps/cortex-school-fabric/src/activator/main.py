#!/usr/bin/env python3
"""
School Fabric Activator

Handles learning and content operations via Cortex School services.
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
FABRIC_NAME = os.getenv("FABRIC_NAME", "school")
REDIS_HOST = os.getenv("REDIS_HOST", "redis.cortex-chat.svc.cluster.local")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
TASK_STREAM = os.getenv("TASK_STREAM", "cortex.school.tasks")
RESULT_STREAM = os.getenv("RESULT_STREAM", "cortex.results")
CONSUMER_GROUP = os.getenv("CONSUMER_GROUP", "school-activator")
COORDINATOR_URL = os.getenv("COORDINATOR_URL", "http://school-coordinator.cortex-school.svc.cluster.local:8080")
RAG_VALIDATOR_URL = os.getenv("RAG_VALIDATOR_URL", "http://rag-validator.cortex-school.svc.cluster.local:8080")
BLOG_WRITER_URL = os.getenv("BLOG_WRITER_URL", "http://blog-writer.cortex-school.svc.cluster.local:8080")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://cortex-school-mcp.cortex-school.svc.cluster.local:3000")
AGENT_ID = f"{FABRIC_NAME}-{uuid.uuid4().hex[:8]}"

# Global state
redis_client: Optional[redis.Redis] = None
running = False


class QueryRequest(BaseModel):
    query: str
    context: Optional[dict] = None


class QueryResponse(BaseModel):
    success: bool
    response: str
    tool_calls: int = 0
    latency_ms: int = 0


async def call_school_service(endpoint: str, method: str = "GET", data: Dict[str, Any] = None) -> Any:
    """Call a Cortex School service endpoint."""
    # Determine which service to call based on endpoint
    if endpoint.startswith("/api/modules") or endpoint.startswith("/api/progress") or endpoint.startswith("/api/quizzes") or endpoint.startswith("/api/search"):
        base_url = COORDINATOR_URL
    elif endpoint.startswith("/api/validate"):
        base_url = RAG_VALIDATOR_URL
    elif endpoint.startswith("/api/blog"):
        base_url = BLOG_WRITER_URL
    else:
        base_url = COORDINATOR_URL

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            url = f"{base_url}{endpoint}"
            if method == "GET":
                response = await client.get(url, params=data)
            else:
                response = await client.post(url, json=data)

            if response.status_code in [200, 201]:
                return response.json()
            else:
                return {"error": f"Service returned {response.status_code}: {response.text}"}
        except httpx.TimeoutException:
            return {"error": "School service request timed out"}
        except Exception as e:
            return {"error": str(e)}


async def process_query(query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Process a query using Cortex School services."""
    start = time.time()
    tool_calls = 0
    query_lower = query.lower()

    # Route based on keywords
    if "module" in query_lower:
        if "list" in query_lower or "show" in query_lower or "all" in query_lower:
            result = await call_school_service("/api/modules", "GET")
            tool_calls = 1
        elif "create" in query_lower:
            result = {"message": "To create a learning module, provide: title, source videos, difficulty level, and tags."}
        elif "progress" in query_lower:
            result = await call_school_service("/api/progress", "GET")
            tool_calls = 1
        else:
            result = await call_school_service("/api/modules", "GET")
            tool_calls = 1

    elif "quiz" in query_lower:
        if "generate" in query_lower or "create" in query_lower:
            result = {"message": "To generate a quiz, provide a module_id. Use 'list modules' to see available modules."}
        else:
            result = {"message": "Quiz capabilities: generate quizzes from learning modules. Provide a module_id to get started."}

    elif "blog" in query_lower:
        if "generate" in query_lower or "create" in query_lower or "write" in query_lower:
            # Extract topic if provided
            result = {"message": "To generate a blog post, provide: topic, optional source modules, style (technical/casual/tutorial), and length (short/medium/long)."}
        else:
            result = {"message": "Blog capabilities: generate blog posts from learning content. Specify a topic to get started."}

    elif "validate" in query_lower or "validation" in query_lower:
        result = {"message": "RAG validation: validates generated content against source references. Provide content text and optional source document IDs."}

    elif "search" in query_lower or "knowledge" in query_lower:
        # Extract search query
        search_terms = query_lower.replace("search", "").replace("knowledge", "").replace("for", "").strip()
        if search_terms:
            result = await call_school_service("/api/search", "POST", {"query": search_terms})
            tool_calls = 1
        else:
            result = {"message": "Knowledge search: search the school knowledge base. Provide a search query."}

    elif "progress" in query_lower or "learning" in query_lower:
        result = await call_school_service("/api/progress", "GET")
        tool_calls = 1

    else:
        # Default: show school capabilities
        result = {
            "message": "Cortex School fabric ready. Available capabilities:",
            "capabilities": [
                "List and create learning modules",
                "Generate quizzes from modules",
                "Generate blog posts from content",
                "Validate RAG-generated content",
                "Search the knowledge base",
                "Track learning progress"
            ],
            "services": {
                "coordinator": COORDINATOR_URL,
                "rag_validator": RAG_VALIDATOR_URL,
                "blog_writer": BLOG_WRITER_URL
            }
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

    logger.info("school_activator_starting", fabric=FABRIC_NAME)

    # Connect to Redis
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD if REDIS_PASSWORD else None,
        decode_responses=False
    )
    await redis_client.ping()
    logger.info("redis_connected", host=REDIS_HOST)

    # Start task consumer
    running = True
    consumer_task = asyncio.create_task(consume_tasks())

    logger.info("school_activator_ready")

    yield

    # Shutdown
    logger.info("school_activator_stopping")
    running = False
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    await redis_client.close()


app = FastAPI(
    title="School Fabric Activator",
    description="Learning and content operations via Cortex School",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health():
    """Health check."""
    redis_ok = redis_client is not None
    return {
        "status": "healthy" if redis_ok else "degraded",
        "service": "school-activator",
        "fabric": FABRIC_NAME,
        "redis_connected": redis_ok
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


@app.get("/capabilities")
async def list_capabilities():
    """List school fabric capabilities."""
    return {
        "fabric": FABRIC_NAME,
        "capabilities": [
            "Learning module management",
            "Quiz generation",
            "Blog post creation",
            "RAG content validation",
            "Knowledge base search",
            "Learning progress tracking"
        ],
        "services": {
            "coordinator": COORDINATOR_URL,
            "rag_validator": RAG_VALIDATOR_URL,
            "blog_writer": BLOG_WRITER_URL,
            "mcp": MCP_SERVER_URL
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
