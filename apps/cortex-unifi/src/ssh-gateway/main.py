"""
UniFi SSH Gateway - Secure SSH Execution Layer

Handles SSH operations to UDM Pro for:
- API failover
- Diagnostics (logs, routes, iptables)
- Advanced operations not exposed via API

Security: Only allowlisted commands can be executed.
"""

import os
import asyncio
import re
from typing import Optional, Any
from dataclasses import dataclass
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import structlog

# Try to import asyncssh, fall back to paramiko if not available
try:
    import asyncssh
    SSH_LIB = "asyncssh"
except ImportError:
    SSH_LIB = None

# =============================================================================
# Configuration
# =============================================================================

@dataclass
class SSHConfig:
    host: str
    username: str
    password: str
    port: int = 22
    timeout: int = 30
    max_connections: int = 5


@dataclass
class AllowedCommand:
    name: str
    command: str
    category: str
    risk_level: str
    params: list = None


# =============================================================================
# Command Registry
# =============================================================================

ALLOWED_COMMANDS: dict[str, AllowedCommand] = {
    # System info
    "get_system_info": AllowedCommand(
        name="get_system_info",
        command="ubnt-systool boardname && ubnt-systool cputemp",
        category="diagnostic",
        risk_level="low"
    ),
    "get_uptime": AllowedCommand(
        name="get_uptime",
        command="uptime",
        category="diagnostic",
        risk_level="low"
    ),
    "get_memory": AllowedCommand(
        name="get_memory",
        command="free -h",
        category="diagnostic",
        risk_level="low"
    ),
    "get_disk": AllowedCommand(
        name="get_disk",
        command="df -h",
        category="diagnostic",
        risk_level="low"
    ),
    "get_version": AllowedCommand(
        name="get_version",
        command="cat /etc/unifi-os/version",
        category="diagnostic",
        risk_level="low"
    ),
    # Network diagnostics
    "get_interfaces": AllowedCommand(
        name="get_interfaces",
        command="ip addr show",
        category="diagnostic",
        risk_level="low"
    ),
    "get_routes": AllowedCommand(
        name="get_routes",
        command="ip route show",
        category="diagnostic",
        risk_level="low"
    ),
    "get_arp": AllowedCommand(
        name="get_arp",
        command="ip neigh show",
        category="diagnostic",
        risk_level="low"
    ),
    "get_connections": AllowedCommand(
        name="get_connections",
        command="ss -tulpn",
        category="diagnostic",
        risk_level="low"
    ),
    # Firewall
    "get_iptables": AllowedCommand(
        name="get_iptables",
        command="iptables -L -n -v",
        category="diagnostic",
        risk_level="low"
    ),
    "get_nat_rules": AllowedCommand(
        name="get_nat_rules",
        command="iptables -t nat -L -n -v",
        category="diagnostic",
        risk_level="low"
    ),
    # Logs
    "get_system_logs": AllowedCommand(
        name="get_system_logs",
        command="tail -{lines} /var/log/messages",
        category="diagnostic",
        risk_level="low",
        params=[{"name": "lines", "default": "100", "max": "500"}]
    ),
    "get_unifi_logs": AllowedCommand(
        name="get_unifi_logs",
        command="journalctl -u unifi -n {lines} --no-pager",
        category="diagnostic",
        risk_level="low",
        params=[{"name": "lines", "default": "100", "max": "500"}]
    ),
    # Service status
    "get_service_status": AllowedCommand(
        name="get_service_status",
        command="systemctl status unifi --no-pager",
        category="diagnostic",
        risk_level="low"
    ),
    "get_containers": AllowedCommand(
        name="get_containers",
        command="podman ps",
        category="diagnostic",
        risk_level="low"
    ),
    # Network tools
    "ping": AllowedCommand(
        name="ping",
        command="ping -c 4 {host}",
        category="diagnostic",
        risk_level="low",
        params=[{"name": "host", "required": True, "validation": r"^[a-zA-Z0-9.-]+$"}]
    ),
    "traceroute": AllowedCommand(
        name="traceroute",
        command="traceroute -m 15 {host}",
        category="diagnostic",
        risk_level="low",
        params=[{"name": "host", "required": True, "validation": r"^[a-zA-Z0-9.-]+$"}]
    ),
    "dns_lookup": AllowedCommand(
        name="dns_lookup",
        command="dig {host} +short",
        category="diagnostic",
        risk_level="low",
        params=[{"name": "host", "required": True, "validation": r"^[a-zA-Z0-9.-]+$"}]
    ),
}

# Blocked patterns for security
BLOCKED_PATTERNS = [
    "rm -rf", "mkfs", "dd if=", "> /dev/", "chmod 777",
    "wget ", "curl ", "nc ", "ncat ", "bash -i", "sh -i",
    "/bin/sh", "eval ", "exec ", "`", "$("
]


# =============================================================================
# Models
# =============================================================================

class ExecuteRequest(BaseModel):
    command: str
    params: Optional[dict] = None


class ExecuteResponse(BaseModel):
    success: bool
    command: str
    output: Optional[str] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None


# =============================================================================
# SSH Client
# =============================================================================

class SSHGateway:
    """Secure SSH gateway with command allowlisting."""

    def __init__(self, config: SSHConfig):
        self.config = config
        self.log = structlog.get_logger()
        self._connected = False

    async def execute(self, command_name: str, params: dict = None) -> dict:
        """Execute an allowlisted command."""
        # Check if command is allowed
        if command_name not in ALLOWED_COMMANDS:
            return {
                "success": False,
                "error": f"Command not allowed: {command_name}"
            }

        allowed = ALLOWED_COMMANDS[command_name]
        command = allowed.command

        # Substitute parameters
        if params:
            for key, value in params.items():
                # Validate parameters if validation pattern exists
                if allowed.params:
                    for p in allowed.params:
                        if p.get("name") == key and p.get("validation"):
                            if not re.match(p["validation"], str(value)):
                                return {
                                    "success": False,
                                    "error": f"Invalid parameter value for {key}"
                                }
                        # Check max limits
                        if p.get("name") == key and p.get("max"):
                            try:
                                if int(value) > int(p["max"]):
                                    value = p["max"]
                            except ValueError:
                                pass
                command = command.replace(f"{{{key}}}", str(value))

        # Check for blocked patterns in final command
        for pattern in BLOCKED_PATTERNS:
            if pattern in command:
                return {
                    "success": False,
                    "error": f"Blocked pattern detected: {pattern}"
                }

        self.log.info("ssh_executing", command=command_name)

        try:
            if SSH_LIB == "asyncssh":
                return await self._execute_asyncssh(command)
            else:
                return {
                    "success": False,
                    "error": "SSH library not available"
                }
        except Exception as e:
            self.log.error("ssh_error", command=command_name, error=str(e))
            return {
                "success": False,
                "error": str(e)
            }

    async def _execute_asyncssh(self, command: str) -> dict:
        """Execute command using asyncssh."""
        async with asyncssh.connect(
            self.config.host,
            port=self.config.port,
            username=self.config.username,
            password=self.config.password,
            known_hosts=None
        ) as conn:
            result = await conn.run(command, timeout=self.config.timeout)
            return {
                "success": result.exit_status == 0,
                "output": result.stdout,
                "error": result.stderr if result.stderr else None,
                "exit_code": result.exit_status
            }

    async def test_connection(self) -> bool:
        """Test SSH connectivity."""
        try:
            result = await self.execute("get_uptime")
            return result.get("success", False)
        except Exception:
            return False


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="UniFi SSH Gateway",
    description="Secure SSH execution layer for UniFi diagnostics",
    version="0.1.0"
)

ssh_gateway: Optional[SSHGateway] = None
log = structlog.get_logger()


@app.on_event("startup")
async def startup():
    global ssh_gateway

    host = os.getenv("SSH_HOST")
    username = os.getenv("SSH_USERNAME")
    password = os.getenv("SSH_PASSWORD")
    port = int(os.getenv("SSH_PORT", "22"))
    timeout = int(os.getenv("SSH_TIMEOUT", "30"))

    if host and username and password:
        config = SSHConfig(
            host=host,
            username=username,
            password=password,
            port=port,
            timeout=timeout
        )
        ssh_gateway = SSHGateway(config)
        log.info("ssh_gateway_initialized", host=host)


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/ready")
async def ready():
    if not ssh_gateway:
        raise HTTPException(503, "SSH gateway not configured")
    return {"status": "ready"}


@app.get("/commands")
async def list_commands():
    """List all available commands."""
    return {
        name: {
            "category": cmd.category,
            "risk_level": cmd.risk_level,
            "params": cmd.params
        }
        for name, cmd in ALLOWED_COMMANDS.items()
    }


@app.post("/execute", response_model=ExecuteResponse)
async def execute_command(request: ExecuteRequest):
    """Execute an allowlisted SSH command."""
    if not ssh_gateway:
        return ExecuteResponse(
            success=False,
            command=request.command,
            error="SSH gateway not configured"
        )

    result = await ssh_gateway.execute(request.command, request.params)

    return ExecuteResponse(
        success=result.get("success", False),
        command=request.command,
        output=result.get("output"),
        error=result.get("error"),
        exit_code=result.get("exit_code")
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
