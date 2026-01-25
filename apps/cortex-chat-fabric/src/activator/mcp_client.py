#!/usr/bin/env python3
"""
MCP Client - Direct MCP server integration for fallback

When fabric dispatch fails or for direct tool calls, this client
handles communication with MCP servers.
"""
import json
from typing import Dict, Any, List, Optional

import yaml
import httpx
from anthropic import AsyncAnthropic
import structlog

logger = structlog.get_logger()


class MCPClient:
    """
    Client for direct MCP server communication.

    Used as fallback when fabric routing isn't available or for
    domains without a dedicated fabric.
    """

    def __init__(self):
        self.servers: Dict[str, str] = {}
        self.tools: List[Dict[str, Any]] = []
        self.tool_to_server: Dict[str, Dict[str, str]] = {}

    async def load_server_config(self, config_path: str):
        """Load MCP server configuration from YAML."""
        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)

            servers = config.get("servers", [])
            for server in servers:
                name = server.get("name")
                url = server.get("url")
                if name and url:
                    self.servers[name] = url

            logger.info("mcp_servers_loaded", count=len(self.servers))

        except FileNotFoundError:
            logger.warning("mcp_config_not_found", path=config_path)
            # Use defaults
            self.servers = {
                "cortex-mcp": "http://cortex-mcp-server.cortex-system.svc.cluster.local:3000",
                "proxmox-mcp": "http://proxmox-mcp-server.cortex-system.svc.cluster.local:3000",
                "unifi-mcp": "http://unifi-mcp-server.cortex-system.svc.cluster.local:3000",
                "sandfly-mcp": "http://sandfly-mcp-server.cortex-system.svc.cluster.local:3000",
            }

    async def discover_tools(self):
        """Fetch available tools from all MCP servers."""
        self.tools = []
        self.tool_to_server = {}

        async with httpx.AsyncClient(timeout=10.0) as client:
            for server_name, server_url in self.servers.items():
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

                            self.tool_to_server[prefixed_name] = {
                                "server": server_name,
                                "url": server_url,
                                "original_name": tool_name
                            }

                            self.tools.append({
                                "name": prefixed_name,
                                "description": f"[{server_name}] {tool.get('description', '')}",
                                "input_schema": tool.get("inputSchema", {"type": "object", "properties": {}})
                            })

                        logger.info("mcp_tools_discovered",
                                    server=server_name,
                                    count=len(tools))

                except Exception as e:
                    logger.error("mcp_discovery_error",
                                 server=server_name,
                                 error=str(e))

        logger.info("mcp_discovery_complete", total_tools=len(self.tools))

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool on its MCP server."""
        if tool_name not in self.tool_to_server:
            return {"error": f"Unknown tool: {tool_name}"}

        tool_info = self.tool_to_server[tool_name]
        server_url = tool_info["url"]
        original_name = tool_info["original_name"]

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    server_url,
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "params": {
                            "name": original_name,
                            "arguments": arguments
                        },
                        "id": 1
                    }
                )

                if response.status_code == 200:
                    data = response.json()

                    if "error" in data:
                        return {"error": data["error"]}

                    result = data.get("result", {})

                    # Extract content from MCP response format
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

    async def check_health(self, server_name: str) -> bool:
        """Check if an MCP server is healthy."""
        if server_name not in self.servers:
            return False

        server_url = self.servers[server_name]

        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(f"{server_url}/health")
                return response.status_code == 200
            except Exception:
                return False

    async def chat(self, message: str, history: List[Dict[str, Any]],
                   api_key: str, model: str = "claude-sonnet-4-20250514") -> Dict[str, Any]:
        """
        Process a chat message using Claude with MCP tools.

        This is the fallback when fabric routing isn't available.
        """
        client = AsyncAnthropic(api_key=api_key)

        # Build messages from history
        messages = []
        for msg in history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        # Add current message
        messages.append({"role": "user", "content": message})

        # System prompt
        system_prompt = """You are Cortex, an AI infrastructure assistant with direct access to MCP servers.

You have tools to interact with:
- Proxmox: Virtual machines, containers, nodes, storage
- UniFi: Network devices, clients, sites, WiFi
- Sandfly: Security scans, host analysis, vulnerabilities
- Cortex: Cross-system queries

IMPORTANT: When users ask about infrastructure, actively USE your tools to fetch real data.
Be concise and present data clearly."""

        tool_calls_made = 0
        max_iterations = 10

        try:
            for iteration in range(max_iterations):
                response = await client.messages.create(
                    model=model,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=messages,
                    tools=self.tools if self.tools else None
                )

                if response.stop_reason == "tool_use":
                    # Process tool calls
                    tool_results = []
                    assistant_content = []

                    for block in response.content:
                        if block.type == "tool_use":
                            tool_name = block.name
                            tool_input = block.input
                            tool_use_id = block.id

                            logger.info("mcp_tool_call",
                                        tool=tool_name,
                                        input_preview=str(tool_input)[:100])

                            result = await self.call_tool(tool_name, tool_input)
                            result_str = json.dumps(result) if isinstance(result, (dict, list)) else str(result)

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": result_str[:10000]
                            })
                            assistant_content.append(block)
                            tool_calls_made += 1

                        elif block.type == "text":
                            assistant_content.append(block)

                    # Add to conversation
                    messages.append({"role": "assistant", "content": assistant_content})
                    messages.append({"role": "user", "content": tool_results})

                else:
                    # No more tool calls - extract final response
                    final_response = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_response += block.text

                    return {
                        "response": final_response,
                        "tool_calls": tool_calls_made
                    }

            # Max iterations reached
            return {
                "response": "I ran into complexity processing that request. Please try a more specific query.",
                "tool_calls": tool_calls_made
            }

        except Exception as e:
            logger.error("mcp_chat_error", error=str(e))
            return {
                "response": f"I'm having trouble connecting to my AI backend. Error: {str(e)}",
                "tool_calls": 0
            }
