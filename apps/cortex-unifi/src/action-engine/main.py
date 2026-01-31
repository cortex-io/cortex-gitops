"""
UniFi Action Engine - API Operations Layer

Handles all UniFi API operations via UI.com Cloud API ONLY.
Uses https://api.ui.com/v1/ with X-API-KEY header.

NO legacy API, NO local controller access.
"""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
from datetime import datetime
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import structlog

# =============================================================================
# Configuration
# =============================================================================

# UI.com Cloud API - THE ONLY API WE USE
UNIFI_API_BASE = os.getenv("UNIFI_API_BASE", "https://api.ui.com")
UNIFI_API_KEY = os.getenv("UNIFI_API_KEY", "")
UNIFI_API_VERSION = os.getenv("UNIFI_API_VERSION", "v1")

API_BASE = f"{UNIFI_API_BASE.rstrip('/')}/{UNIFI_API_VERSION}"

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ActionDefinition:
    name: str
    method: str
    endpoint: str
    category: str
    risk_level: RiskLevel
    requires_confirmation: bool = False


# =============================================================================
# UniFi Cloud API Client
# =============================================================================

class UniFiCloudClient:
    """Client for UI.com Cloud API."""

    def __init__(self, api_key: str, api_base: str = API_BASE):
        self.api_key = api_key
        self.api_base = api_base
        self.log = structlog.get_logger()

    def _headers(self) -> dict:
        """Get headers for API requests."""
        return {
            "X-API-KEY": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    async def request(
        self,
        method: str,
        endpoint: str,
        json: Optional[dict] = None,
        params: Optional[dict] = None
    ) -> dict:
        """Make a request to the UI.com Cloud API."""
        url = f"{self.api_base}/{endpoint.lstrip('/')}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(
                method=method,
                url=url,
                json=json,
                params=params,
                headers=self._headers()
            )

            if resp.status_code >= 400:
                self.log.error(
                    "api_error",
                    status=resp.status_code,
                    url=url,
                    response=resp.text[:500]
                )
                raise Exception(f"API error: {resp.status_code} - {resp.text[:200]}")

            return resp.json()

    async def get_hosts(self) -> list:
        """Get all hosts (consoles)."""
        result = await self.request("GET", "/hosts")
        return result.get("data", [])

    async def get_sites(self) -> list:
        """Get all sites."""
        result = await self.request("GET", "/sites")
        return result.get("data", [])

    async def get_devices(self, host_id: Optional[str] = None) -> list:
        """Get all devices, optionally filtered by host."""
        params = {"hostId": host_id} if host_id else None
        result = await self.request("GET", "/devices", params=params)
        return result.get("data", [])

    async def get_device(self, device_id: str) -> dict:
        """Get a specific device."""
        result = await self.request("GET", f"/devices/{device_id}")
        return result.get("data", result)


# =============================================================================
# Action Registry
# =============================================================================

ACTIONS: dict[str, ActionDefinition] = {
    # Host operations
    "list_hosts": ActionDefinition(
        name="list_hosts",
        method="GET",
        endpoint="/hosts",
        category="read",
        risk_level=RiskLevel.LOW
    ),
    "get_host": ActionDefinition(
        name="get_host",
        method="GET",
        endpoint="/hosts/{host_id}",
        category="read",
        risk_level=RiskLevel.LOW
    ),

    # Site operations
    "list_sites": ActionDefinition(
        name="list_sites",
        method="GET",
        endpoint="/sites",
        category="read",
        risk_level=RiskLevel.LOW
    ),
    "get_site": ActionDefinition(
        name="get_site",
        method="GET",
        endpoint="/sites/{site_id}",
        category="read",
        risk_level=RiskLevel.LOW
    ),

    # Device operations
    "list_devices": ActionDefinition(
        name="list_devices",
        method="GET",
        endpoint="/devices",
        category="read",
        risk_level=RiskLevel.LOW
    ),
    "get_device": ActionDefinition(
        name="get_device",
        method="GET",
        endpoint="/devices/{device_id}",
        category="read",
        risk_level=RiskLevel.LOW
    ),
}


# =============================================================================
# Models
# =============================================================================

class ExecuteRequest(BaseModel):
    tool: str
    query: str
    context: Optional[dict] = None
    params: Optional[dict] = None
    confirmed: bool = False


class ExecuteResponse(BaseModel):
    success: bool
    tool: str
    result: Optional[Any] = None
    error: Optional[str] = None
    requires_confirmation: bool = False
    risk_level: str = "low"
    audit_id: Optional[str] = None


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="UniFi Action Engine",
    description="Execution layer for UniFi Cloud API operations",
    version="0.2.0"
)

# Initialize client from environment
unifi_client: Optional[UniFiCloudClient] = None
log = structlog.get_logger()


@app.on_event("startup")
async def startup():
    global unifi_client

    api_key = os.getenv("UNIFI_API_KEY")

    if api_key:
        unifi_client = UniFiCloudClient(api_key)
        log.info("unifi_cloud_client_initialized", api_base=API_BASE)
    else:
        log.warning("unifi_api_key_not_set")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "api_base": API_BASE,
        "api_key_configured": bool(UNIFI_API_KEY)
    }


@app.get("/actions")
async def list_actions():
    """List available actions."""
    return {
        "actions": [
            {
                "name": action.name,
                "method": action.method,
                "endpoint": action.endpoint,
                "category": action.category,
                "risk_level": action.risk_level.value,
                "requires_confirmation": action.requires_confirmation
            }
            for action in ACTIONS.values()
        ]
    }


@app.post("/execute", response_model=ExecuteResponse)
async def execute_action(request: ExecuteRequest):
    """Execute a UniFi action."""
    if not unifi_client:
        raise HTTPException(status_code=503, detail="UniFi client not initialized")

    action = ACTIONS.get(request.tool)
    if not action:
        return ExecuteResponse(
            success=False,
            tool=request.tool,
            error=f"Unknown action: {request.tool}"
        )

    # Check confirmation for risky actions
    if action.requires_confirmation and not request.confirmed:
        return ExecuteResponse(
            success=False,
            tool=request.tool,
            requires_confirmation=True,
            risk_level=action.risk_level.value,
            error="This action requires confirmation"
        )

    try:
        # Build endpoint with params
        endpoint = action.endpoint
        if request.params:
            for key, value in request.params.items():
                endpoint = endpoint.replace(f"{{{key}}}", str(value))

        # Execute the action
        result = await unifi_client.request(
            method=action.method,
            endpoint=endpoint,
            json=request.context
        )

        return ExecuteResponse(
            success=True,
            tool=request.tool,
            result=result,
            risk_level=action.risk_level.value,
            audit_id=f"action-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )

    except Exception as e:
        log.error("action_failed", tool=request.tool, error=str(e))
        return ExecuteResponse(
            success=False,
            tool=request.tool,
            error=str(e),
            risk_level=action.risk_level.value
        )


@app.get("/hosts")
async def get_hosts():
    """Get all UniFi hosts."""
    if not unifi_client:
        raise HTTPException(status_code=503, detail="UniFi client not initialized")

    try:
        hosts = await unifi_client.get_hosts()
        return {"ok": True, "count": len(hosts), "hosts": hosts}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/sites")
async def get_sites():
    """Get all UniFi sites."""
    if not unifi_client:
        raise HTTPException(status_code=503, detail="UniFi client not initialized")

    try:
        sites = await unifi_client.get_sites()
        return {"ok": True, "count": len(sites), "sites": sites}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/devices")
async def get_devices(host_id: Optional[str] = None):
    """Get all UniFi devices."""
    if not unifi_client:
        raise HTTPException(status_code=503, detail="UniFi client not initialized")

    try:
        devices = await unifi_client.get_devices(host_id)
        return {"ok": True, "count": len(devices), "devices": devices}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/status")
async def get_status():
    """Get comprehensive network status."""
    if not unifi_client:
        raise HTTPException(status_code=503, detail="UniFi client not initialized")

    try:
        hosts = await unifi_client.get_hosts()
        sites = await unifi_client.get_sites()
        devices = await unifi_client.get_devices()

        # Count device states
        online = sum(1 for d in devices if d.get("reportedState", {}).get("state") == "connected")
        offline = len(devices) - online

        return {
            "ok": True,
            "summary": {
                "hosts": len(hosts),
                "sites": len(sites),
                "devices": {
                    "total": len(devices),
                    "online": online,
                    "offline": offline
                }
            }
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
