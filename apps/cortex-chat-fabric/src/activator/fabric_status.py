#!/usr/bin/env python3
"""
Fabric Layer Status - Kubernetes-based status reporting for Cortex

Provides real-time status of:
- Core Infrastructure (layer-activator, fabric-gateway)
- Fabric Activators
- MCP Servers
- General cluster services
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

import httpx
import structlog

logger = structlog.get_logger()

# Kubernetes API configuration
K8S_API_SERVER = os.getenv("KUBERNETES_SERVICE_HOST", "kubernetes.default.svc")
K8S_API_PORT = os.getenv("KUBERNETES_SERVICE_PORT", "443")
K8S_TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"
K8S_CA_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"


class FabricStatusReporter:
    """
    Reports status of all Fabric Layer components using Kubernetes API.
    """

    def __init__(self):
        self._token: Optional[str] = None
        self._token_loaded = False

    def _load_token(self) -> Optional[str]:
        """Load Kubernetes service account token."""
        if self._token_loaded:
            return self._token
        try:
            with open(K8S_TOKEN_PATH, "r") as f:
                self._token = f.read().strip()
            self._token_loaded = True
        except FileNotFoundError:
            logger.warning("k8s_token_not_found", path=K8S_TOKEN_PATH)
            self._token = None
            self._token_loaded = True
        return self._token

    async def _k8s_api_call(self, path: str) -> Optional[Dict[str, Any]]:
        """Make a call to the Kubernetes API."""
        token = self._load_token()
        if not token:
            return None

        url = f"https://{K8S_API_SERVER}:{K8S_API_PORT}{path}"
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(verify=K8S_CA_PATH, timeout=10.0) as client:
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning("k8s_api_error", status=response.status_code, path=path)
                    return None
            except Exception as e:
                logger.error("k8s_api_exception", error=str(e), path=path)
                return None

    async def get_deployments(self, namespace: str = None, label_selector: str = None) -> List[Dict[str, Any]]:
        """Get deployments from Kubernetes."""
        if namespace:
            path = f"/apis/apps/v1/namespaces/{namespace}/deployments"
        else:
            path = "/apis/apps/v1/deployments"

        if label_selector:
            path += f"?labelSelector={label_selector}"

        result = await self._k8s_api_call(path)
        if result:
            return result.get("items", [])
        return []

    async def get_fabric_layer_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of all Fabric Layer components.

        Returns structured status for:
        - Core infrastructure
        - Fabric activators
        - MCP servers
        """
        status = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "core_infrastructure": [],
            "fabric_activators": [],
            "mcp_servers": [],
            "summary": {
                "total_activators": 0,
                "healthy_activators": 0,
                "total_mcp_servers": 0,
                "healthy_mcp_servers": 0,
                "issues": []
            }
        }

        # Get all deployments from relevant namespaces
        all_deployments = []
        for ns in ["cortex-system", "cortex-chat", "cortex-unifi", "cortex-school", "cortex-n8n"]:
            deps = await self.get_deployments(namespace=ns)
            all_deployments.extend(deps)

        # Categorize deployments
        for deploy in all_deployments:
            name = deploy.get("metadata", {}).get("name", "")
            namespace = deploy.get("metadata", {}).get("namespace", "")
            spec = deploy.get("spec", {})
            deploy_status = deploy.get("status", {})

            desired = spec.get("replicas", 0)
            ready = deploy_status.get("readyReplicas", 0) or 0
            available = deploy_status.get("availableReplicas", 0) or 0

            is_healthy = ready >= desired and desired > 0
            health_status = "healthy" if is_healthy else ("scaled-to-zero" if desired == 0 else "degraded")

            deploy_info = {
                "name": name,
                "namespace": namespace,
                "ready": ready,
                "desired": desired,
                "status": health_status
            }

            # Categorize
            if name in ["layer-activator", "fabric-gateway"]:
                status["core_infrastructure"].append(deploy_info)
            elif "mcp" in name.lower():
                status["mcp_servers"].append(deploy_info)
                status["summary"]["total_mcp_servers"] += 1
                if is_healthy:
                    status["summary"]["healthy_mcp_servers"] += 1
                else:
                    status["summary"]["issues"].append(f"{namespace}/{name}: {ready}/{desired} ready")
            elif "activator" in name.lower():
                status["fabric_activators"].append(deploy_info)
                status["summary"]["total_activators"] += 1
                if is_healthy:
                    status["summary"]["healthy_activators"] += 1
                else:
                    status["summary"]["issues"].append(f"{namespace}/{name}: {ready}/{desired} ready")

        # Sort lists by name
        status["core_infrastructure"].sort(key=lambda x: x["name"])
        status["fabric_activators"].sort(key=lambda x: x["name"])
        status["mcp_servers"].sort(key=lambda x: x["name"])

        return status

    def format_status_report(self, status: Dict[str, Any]) -> str:
        """Format status into a readable report string."""
        lines = []
        lines.append("═" * 60)
        lines.append("         FABRIC LAYER STATUS REPORT")
        lines.append("═" * 60)
        lines.append("")

        # Core Infrastructure
        lines.append("┌" + "─" * 58 + "┐")
        lines.append("│ CORE INFRASTRUCTURE" + " " * 38 + "│")
        lines.append("├" + "─" * 58 + "┤")
        for item in status["core_infrastructure"]:
            icon = "✓" if item["status"] == "healthy" else "⚠"
            line = f"│  {icon} {item['name']:<30} {item['ready']}/{item['desired']} ready"
            lines.append(f"{line:<58}│")
        if not status["core_infrastructure"]:
            lines.append("│  (no data available)" + " " * 36 + "│")
        lines.append("└" + "─" * 58 + "┘")
        lines.append("")

        # Fabric Activators
        summary = status["summary"]
        lines.append("┌" + "─" * 58 + "┐")
        act_header = f"│ FABRIC ACTIVATORS ({summary['healthy_activators']}/{summary['total_activators']} healthy)"
        lines.append(f"{act_header:<59}│")
        lines.append("├" + "─" * 58 + "┤")
        for item in status["fabric_activators"]:
            icon = "✓" if item["status"] == "healthy" else ("○" if item["status"] == "scaled-to-zero" else "⚠")
            ns_short = item["namespace"].replace("cortex-", "")[:10]
            line = f"│  {icon} {item['name']:<25} [{ns_short:<10}] {item['ready']}/{item['desired']}"
            lines.append(f"{line:<58}│")
        if not status["fabric_activators"]:
            lines.append("│  (no activators found)" + " " * 34 + "│")
        lines.append("└" + "─" * 58 + "┘")
        lines.append("")

        # MCP Servers
        lines.append("┌" + "─" * 58 + "┐")
        mcp_header = f"│ MCP SERVERS ({summary['healthy_mcp_servers']}/{summary['total_mcp_servers']} healthy)"
        lines.append(f"{mcp_header:<59}│")
        lines.append("├" + "─" * 58 + "┤")
        for item in status["mcp_servers"]:
            icon = "✓" if item["status"] == "healthy" else ("○" if item["status"] == "scaled-to-zero" else "⚠")
            line = f"│  {icon} {item['name']:<40} {item['ready']}/{item['desired']}"
            lines.append(f"{line:<58}│")
        if not status["mcp_servers"]:
            lines.append("│  (no MCP servers found)" + " " * 33 + "│")
        lines.append("└" + "─" * 58 + "┘")

        # Issues
        if summary["issues"]:
            lines.append("")
            lines.append("┌" + "─" * 58 + "┐")
            lines.append("│ ⚠ ISSUES" + " " * 49 + "│")
            lines.append("├" + "─" * 58 + "┤")
            for issue in summary["issues"][:5]:  # Limit to 5 issues
                line = f"│  • {issue}"
                lines.append(f"{line:<58}│")
            lines.append("└" + "─" * 58 + "┘")

        return "\n".join(lines)


async def get_greeting_response(fabric_dispatcher=None, mcp_client=None) -> str:
    """
    Generate a greeting response with Fabric Layer status.

    This is called when users say hello, hi, or ask about system status.
    """
    reporter = FabricStatusReporter()

    try:
        status = await reporter.get_fabric_layer_status()
        report = reporter.format_status_report(status)

        # Build greeting
        summary = status["summary"]
        total_healthy = summary["healthy_activators"] + summary["healthy_mcp_servers"]
        total_components = summary["total_activators"] + summary["total_mcp_servers"]

        if total_components == 0:
            health_msg = "I'm unable to access cluster status at the moment."
        elif total_healthy == total_components:
            health_msg = f"All {total_components} Fabric Layer components are healthy."
        else:
            health_msg = f"{total_healthy}/{total_components} Fabric Layer components are healthy."

        # Add fabric info from dispatcher if available
        fabric_info = ""
        if fabric_dispatcher and hasattr(fabric_dispatcher, 'fabrics'):
            fabric_names = list(fabric_dispatcher.fabrics.keys())
            if fabric_names:
                fabric_info = f"\n\nRegistered fabrics: {', '.join(fabric_names)}"

        # Add MCP tool count if available
        tool_info = ""
        if mcp_client and hasattr(mcp_client, 'tools'):
            tool_count = len(mcp_client.tools)
            if tool_count > 0:
                tool_info = f"\nMCP tools available: {tool_count}"

        greeting = f"""Hello! I'm Cortex, your infrastructure AI assistant.

{health_msg}{fabric_info}{tool_info}

```
{report}
```

How can I help you today? I can assist with:
• **Network**: UniFi devices, WiFi, clients
• **Infrastructure**: Proxmox VMs, Kubernetes pods
• **Security**: Sandfly scans, vulnerability analysis
• **Automation**: n8n workflows, triggers
• **Learning**: School modules, quizzes, content
• **VPN**: Tailscale devices, ACLs, DNS"""

        return greeting

    except Exception as e:
        logger.error("greeting_status_error", error=str(e))
        return f"""Hello! I'm Cortex, your infrastructure AI assistant.

I'm having trouble fetching the current system status, but I'm ready to help.

How can I assist you today? I can help with:
• Network operations (UniFi)
• Infrastructure management (Proxmox, Kubernetes)
• Security analysis (Sandfly)
• Workflow automation (n8n)
• Learning content (School)
• VPN management (Tailscale)"""


def is_greeting(message: str) -> bool:
    """Check if a message is a greeting that should trigger status display."""
    message_lower = message.lower().strip()

    # Direct greetings
    greetings = [
        "hello", "hi", "hey", "howdy", "greetings",
        "good morning", "good afternoon", "good evening",
        "what's up", "whats up", "sup",
        "yo", "hola", "bonjour"
    ]

    for greeting in greetings:
        if message_lower == greeting or message_lower.startswith(greeting + " ") or message_lower.startswith(greeting + ","):
            return True

    # Status-related queries that should show fabric status
    status_queries = [
        "status", "system status", "fabric status",
        "how are you", "are you there", "are you working",
        "what can you do", "help me", "what are your capabilities"
    ]

    for query in status_queries:
        if query in message_lower:
            return True

    return False
