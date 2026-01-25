#!/usr/bin/env python3
"""
Chat Fabric Activator - Master Orchestrator for Cortex Chat

This is the central hub that:
1. Receives chat requests from frontend
2. Classifies intent using Claude Haiku
3. Routes to appropriate domain fabrics via Redis Streams
4. Falls back to direct MCP calls if fabric unavailable
5. Aggregates responses back to users
6. Manages conversation state in Redis
"""
import os
import json
import uuid
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from redis_client import RedisClient, ConversationStore
from fabric_dispatcher import FabricDispatcher
from mcp_client import MCPClient
from intent_classifier import IntentClassifier

# Configure structured logging
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
REDIS_HOST = os.getenv("REDIS_HOST", "redis.cortex-chat.svc.cluster.local")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
FABRIC_NAME = os.getenv("FABRIC_NAME", "chat")

# Global clients
redis_client: Optional[RedisClient] = None
conversation_store: Optional[ConversationStore] = None
fabric_dispatcher: Optional[FabricDispatcher] = None
mcp_client: Optional[MCPClient] = None
intent_classifier: Optional[IntentClassifier] = None


# Request/Response models
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    expert: str
    tool_calls: int = 0
    fabric_used: Optional[str] = None
    timestamp: str


class ConversationCreate(BaseModel):
    title: Optional[str] = None


class StatusUpdate(BaseModel):
    status: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources."""
    global redis_client, conversation_store, fabric_dispatcher, mcp_client, intent_classifier

    logger.info("chat_activator_starting", fabric=FABRIC_NAME)

    # Initialize Redis
    redis_client = RedisClient(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD
    )
    await redis_client.connect()

    # Initialize conversation store
    conversation_store = ConversationStore(redis_client)

    # Initialize fabric dispatcher
    fabric_dispatcher = FabricDispatcher(redis_client)
    await fabric_dispatcher.load_fabric_config("/config/fabrics.yaml")

    # Initialize MCP client for direct calls
    mcp_client = MCPClient()
    await mcp_client.load_server_config("/config/mcp-servers.yaml")
    await mcp_client.discover_tools()

    # Initialize intent classifier
    intent_classifier = IntentClassifier(
        api_key=ANTHROPIC_API_KEY,
        fabric_dispatcher=fabric_dispatcher
    )

    logger.info("chat_activator_ready",
                fabrics=list(fabric_dispatcher.fabrics.keys()),
                mcp_tools=len(mcp_client.tools))

    yield

    # Cleanup
    logger.info("chat_activator_stopping")
    await redis_client.disconnect()


app = FastAPI(
    title="Chat Fabric Activator",
    description="Master orchestrator for Cortex Chat",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check endpoint."""
    redis_ok = redis_client.connected if redis_client else False
    return {
        "status": "healthy" if redis_ok else "degraded",
        "service": "chat-activator",
        "fabric": FABRIC_NAME,
        "redis_connected": redis_ok,
        "mcp_tools_loaded": len(mcp_client.tools) if mcp_client else 0,
        "fabrics_registered": len(fabric_dispatcher.fabrics) if fabric_dispatcher else 0
    }


@app.get("/ready")
async def ready():
    """Readiness check."""
    if not redis_client or not redis_client.connected:
        raise HTTPException(status_code=503, detail="Redis not connected")
    return {"status": "ready"}


# =============================================================================
# Authentication (mock for now)
# =============================================================================
@app.post("/api/auth/login")
async def login(data: dict = {}):
    """Mock authentication endpoint."""
    username = data.get("username", "user")
    return {
        "success": True,
        "token": "mock-token-123",
        "username": username,
        "user": {"username": username, "id": "user-1"}
    }


# =============================================================================
# Conversation Management
# =============================================================================
@app.get("/api/conversations")
async def list_conversations(status: Optional[str] = None, include_archived: bool = False):
    """List all conversations."""
    conversations = await conversation_store.list_conversations(
        status_filter=status,
        include_archived=include_archived
    )
    return conversations


@app.post("/api/conversations")
async def create_conversation(data: ConversationCreate):
    """Create a new conversation."""
    conv = await conversation_store.create_conversation(title=data.title)
    return conv


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a single conversation, auto-creating if it doesn't exist."""
    conv = await conversation_store.get_conversation(conversation_id)
    if not conv:
        # Auto-create new conversations (frontend generates session IDs upfront)
        conv = await conversation_store.create_conversation(conv_id=conversation_id)
    return conv


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation permanently."""
    success = await conversation_store.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"success": True, "message": f"Conversation {conversation_id} deleted"}


@app.post("/api/conversations/{conversation_id}/archive")
async def archive_conversation(conversation_id: str):
    """Archive a conversation."""
    success = await conversation_store.archive_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"success": True, "message": f"Conversation {conversation_id} archived"}


@app.post("/api/conversations/{conversation_id}/restore")
async def restore_conversation(conversation_id: str):
    """Restore an archived conversation."""
    success = await conversation_store.restore_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Archived conversation not found")
    return {"success": True, "message": f"Conversation {conversation_id} restored"}


@app.put("/api/conversations/{conversation_id}/status")
async def update_conversation_status(conversation_id: str, data: StatusUpdate):
    """Update conversation status."""
    if data.status not in ["active", "in_progress", "completed"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    conv = await conversation_store.update_status(conversation_id, data.status)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@app.get("/api/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str):
    """Get conversation message history."""
    messages = await conversation_store.get_messages(conversation_id)
    return messages


# =============================================================================
# Main Chat Endpoint
# =============================================================================
@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Main chat endpoint - the heart of the Chat Fabric Activator.
    Returns Server-Sent Events (SSE) for streaming response to frontend.

    Flow:
    1. Get or create conversation
    2. Store user message
    3. Classify intent to determine routing
    4. Try fabric dispatch first, fall back to direct MCP
    5. Stream response back via SSE
    """
    async def generate_sse():
        try:
            # Support both conversation_id and session_id (frontend uses session_id)
            conversation_id = request.conversation_id or request.session_id or f"conv-{uuid.uuid4().hex[:8]}"
            now = datetime.utcnow().isoformat() + "Z"

            logger.info("chat_request",
                        conversation_id=conversation_id,
                        message_preview=request.message[:50])

            # Get or create conversation
            conv = await conversation_store.get_conversation(conversation_id)
            if not conv:
                conv = await conversation_store.create_conversation(conv_id=conversation_id)

            # Store user message
            await conversation_store.add_message(conversation_id, "user", request.message)
            await conversation_store.update_status(conversation_id, "in_progress")

            # Classify intent
            intent = await intent_classifier.classify(request.message)
            expert = intent.get("expert", "general")
            target_fabric = intent.get("fabric")

            logger.info("intent_classified", expert=expert, fabric=target_fabric)

            # Try to dispatch to fabric
            response_text = None
            fabric_used = None
            tool_calls = 0

            if target_fabric and fabric_dispatcher.has_fabric(target_fabric):
                try:
                    # Get conversation history for context
                    history = await conversation_store.get_messages(conversation_id)

                    # Dispatch to fabric
                    result = await fabric_dispatcher.dispatch(
                        fabric=target_fabric,
                        query=request.message,
                        context={"history": history[-10:], "conversation_id": conversation_id}
                    )

                    if result.get("success"):
                        response_text = result.get("response")
                        fabric_used = target_fabric
                        tool_calls = result.get("tool_calls", 0)
                        logger.info("fabric_dispatch_success", fabric=target_fabric)

                except asyncio.TimeoutError:
                    logger.warning("fabric_dispatch_timeout", fabric=target_fabric)
                except Exception as e:
                    logger.error("fabric_dispatch_error", fabric=target_fabric, error=str(e))

            # Fall back to direct MCP/Claude if no fabric response
            if not response_text:
                logger.info("using_direct_mcp_fallback")

                # Get conversation history
                history = await conversation_store.get_messages(conversation_id)

                # Use MCP client with Claude
                result = await mcp_client.chat(
                    message=request.message,
                    history=history[-10:],
                    api_key=ANTHROPIC_API_KEY,
                    model=ANTHROPIC_MODEL
                )

                response_text = result.get("response", "I'm having trouble processing that request.")
                tool_calls = result.get("tool_calls", 0)

            # Store assistant response
            await conversation_store.add_message(conversation_id, "assistant", response_text)

            # Stream the response as SSE (frontend expects this format)
            # Send the full response as a single content_block_delta
            yield f"data: {json.dumps({'type': 'content_block_delta', 'delta': response_text})}\n\n"

            # Send completion signal
            yield f"data: {json.dumps({'type': 'message_stop', 'conversation_id': conversation_id, 'expert': expert, 'tool_calls': tool_calls, 'fabric_used': fabric_used})}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error("chat_error", error=str(e))
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.post("/api/chat/json", response_model=ChatResponse)
async def chat_json(request: ChatRequest):
    """
    Non-streaming chat endpoint for programmatic access.
    Returns regular JSON response.
    """
    try:
        # Support both conversation_id and session_id (frontend uses session_id)
        conversation_id = request.conversation_id or request.session_id or f"conv-{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow().isoformat() + "Z"

        logger.info("chat_json_request",
                    conversation_id=conversation_id,
                    message_preview=request.message[:50])

        # Get or create conversation
        conv = await conversation_store.get_conversation(conversation_id)
        if not conv:
            conv = await conversation_store.create_conversation(conv_id=conversation_id)

        # Store user message
        await conversation_store.add_message(conversation_id, "user", request.message)
        await conversation_store.update_status(conversation_id, "in_progress")

        # Classify intent
        intent = await intent_classifier.classify(request.message)
        expert = intent.get("expert", "general")
        target_fabric = intent.get("fabric")

        logger.info("intent_classified", expert=expert, fabric=target_fabric)

        # Try to dispatch to fabric
        response_text = None
        fabric_used = None
        tool_calls = 0

        if target_fabric and fabric_dispatcher.has_fabric(target_fabric):
            try:
                history = await conversation_store.get_messages(conversation_id)
                result = await fabric_dispatcher.dispatch(
                    fabric=target_fabric,
                    query=request.message,
                    context={"history": history[-10:], "conversation_id": conversation_id}
                )
                if result.get("success"):
                    response_text = result.get("response")
                    fabric_used = target_fabric
                    tool_calls = result.get("tool_calls", 0)
            except Exception as e:
                logger.error("fabric_dispatch_error", fabric=target_fabric, error=str(e))

        # Fall back to direct MCP/Claude if no fabric response
        if not response_text:
            history = await conversation_store.get_messages(conversation_id)
            result = await mcp_client.chat(
                message=request.message,
                history=history[-10:],
                api_key=ANTHROPIC_API_KEY,
                model=ANTHROPIC_MODEL
            )
            response_text = result.get("response", "I'm having trouble processing that request.")
            tool_calls = result.get("tool_calls", 0)

        # Store assistant response
        await conversation_store.add_message(conversation_id, "assistant", response_text)

        return ChatResponse(
            response=response_text,
            conversation_id=conversation_id,
            expert=expert,
            tool_calls=tool_calls,
            fabric_used=fabric_used,
            timestamp=now
        )

    except Exception as e:
        logger.error("chat_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# MCP Tools Endpoints
# =============================================================================
@app.get("/api/tools")
async def list_tools():
    """List all available MCP tools."""
    if not mcp_client:
        return {"tools": [], "count": 0, "servers": []}

    return {
        "tools": [{"name": t["name"], "description": t.get("description", "")}
                  for t in mcp_client.tools],
        "count": len(mcp_client.tools),
        "servers": list(mcp_client.servers.keys())
    }


@app.post("/api/tools/refresh")
async def refresh_tools():
    """Refresh the MCP tools cache."""
    if not mcp_client:
        raise HTTPException(status_code=503, detail="MCP client not initialized")

    await mcp_client.discover_tools()
    return {"message": "Tools refreshed", "count": len(mcp_client.tools)}


# =============================================================================
# Status and Service Management
# =============================================================================
@app.get("/api/status")
async def get_system_status():
    """Get status of all connected services and fabrics."""
    status = {
        "fabrics": [],
        "mcp_servers": [],
        "infrastructure": [],
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    # Check fabric health
    if fabric_dispatcher:
        for fabric_name, fabric_info in fabric_dispatcher.fabrics.items():
            fabric_status = await fabric_dispatcher.check_health(fabric_name)
            status["fabrics"].append({
                "name": fabric_name,
                "status": "connected" if fabric_status else "disconnected",
                "capabilities": fabric_info.get("capabilities", [])
            })

    # Check MCP servers
    if mcp_client:
        for server_name, server_url in mcp_client.servers.items():
            server_status = await mcp_client.check_health(server_name)
            status["mcp_servers"].append({
                "name": server_name,
                "status": "connected" if server_status else "disconnected"
            })

    # Check Redis
    status["infrastructure"].append({
        "name": "redis",
        "status": "connected" if (redis_client and redis_client.connected) else "disconnected"
    })

    # Determine overall status
    def get_overall(items):
        if not items:
            return "unknown"
        statuses = [i["status"] for i in items]
        if all(s == "connected" for s in statuses):
            return "healthy"
        elif any(s == "connected" for s in statuses):
            return "degraded"
        return "offline"

    status["overall"] = {
        "fabrics": get_overall(status["fabrics"]),
        "mcp_servers": get_overall(status["mcp_servers"]),
        "infrastructure": get_overall(status["infrastructure"])
    }

    return status


# =============================================================================
# Legacy Route Endpoint (for compatibility)
# =============================================================================
@app.post("/route")
async def route_improvement(data: dict):
    """Legacy MoE Router endpoint for improvement evaluation."""
    # Simplified version - just classify and return
    title = data.get("title", "Untitled")
    category = data.get("category", "unknown")
    relevance = data.get("relevance", 0.0)

    intent = await intent_classifier.classify(f"{title}: {data.get('description', '')}")

    return {
        "expert": intent.get("expert", "general"),
        "evaluation": {
            "category": category,
            "priority": "high" if relevance >= 0.9 else "medium" if relevance >= 0.8 else "low",
            "implementation_complexity": "moderate",
            "risk_level": "low",
            "recommended_action": "auto_approve" if relevance >= 0.9 else "review"
        },
        "reasoning": f"Classified as {intent.get('expert', 'general')} domain",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
