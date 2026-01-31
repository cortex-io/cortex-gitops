#!/usr/bin/env python3
"""
Layer Controller - Dynamic service activation/deactivation for Cortex School

Manages the lifecycle of dependent services based on workflow phases:
- VIDEO: youtube-channel-mcp, youtube-ingestion-mcp, tailscale-mcp
- IMPLEMENT: kubernetes-mcp, github-mcp, github-security-mcp
- WRITE: blog-writer, rag-validator, cortex-mcp

Uses Kubernetes API to scale deployments up/down.
"""
import os
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

import httpx
import structlog

logger = structlog.get_logger()

# Kubernetes API configuration
K8S_API_SERVER = os.getenv("KUBERNETES_SERVICE_HOST", "kubernetes.default.svc")
K8S_API_PORT = os.getenv("KUBERNETES_SERVICE_PORT", "443")
K8S_TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"
K8S_CA_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"


class WorkflowPhase(Enum):
    IDLE = "idle"
    VIDEO = "video"
    ANALYZE = "analyze"
    IMPLEMENT = "implement"
    WRITE = "write"
    COMPLETE = "complete"


# Service dependency graph by phase
PHASE_SERVICES: Dict[WorkflowPhase, List[Dict[str, str]]] = {
    WorkflowPhase.VIDEO: [
        {"name": "youtube-channel-mcp", "namespace": "cortex"},
        {"name": "youtube-ingestion-mcp", "namespace": "cortex"},
        {"name": "tailscale-mcp-server", "namespace": "cortex-system"},
    ],
    WorkflowPhase.ANALYZE: [
        {"name": "cortex-mcp-server", "namespace": "cortex-system"},
        {"name": "moe-router", "namespace": "cortex-school"},
    ],
    WorkflowPhase.IMPLEMENT: [
        {"name": "kubernetes-mcp-server", "namespace": "cortex-system"},
        {"name": "github-mcp-server", "namespace": "cortex-system"},
        {"name": "github-security-mcp-server", "namespace": "cortex-system"},
    ],
    WorkflowPhase.WRITE: [
        {"name": "blog-writer", "namespace": "cortex-school"},
        {"name": "rag-validator", "namespace": "cortex-school"},
        {"name": "cortex-mcp-server", "namespace": "cortex-system"},
    ],
}

# Core services that should always be on during school hours
CORE_SERVICES = [
    {"name": "layer-activator", "namespace": "cortex-system"},
    {"name": "fabric-gateway", "namespace": "cortex-system"},
    {"name": "school-activator", "namespace": "cortex-school"},
    {"name": "school-coordinator", "namespace": "cortex-school"},
    {"name": "github-mcp-server", "namespace": "cortex-system"},
    {"name": "kubernetes-mcp-server", "namespace": "cortex-system"},
    {"name": "cortex-mcp-server", "namespace": "cortex-system"},
]


class LayerController:
    """Controls layer activation/deactivation for workflow phases."""

    def __init__(self):
        self._token: Optional[str] = None
        self._token_loaded = False
        self.current_phase = WorkflowPhase.IDLE
        self.activation_log: List[Dict[str, Any]] = []

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

    async def _k8s_api_call(self, method: str, path: str, body: Dict = None) -> Optional[Dict[str, Any]]:
        """Make a call to the Kubernetes API."""
        token = self._load_token()
        if not token:
            logger.error("no_k8s_token_available")
            return None

        url = f"https://{K8S_API_SERVER}:{K8S_API_PORT}{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/strategic-merge-patch+json" if method == "PATCH" else "application/json"
        }

        async with httpx.AsyncClient(verify=K8S_CA_PATH, timeout=30.0) as client:
            try:
                if method == "GET":
                    response = await client.get(url, headers=headers)
                elif method == "PATCH":
                    response = await client.patch(url, headers=headers, json=body)
                else:
                    response = await client.request(method, url, headers=headers, json=body)

                if response.status_code in [200, 201]:
                    return response.json()
                else:
                    logger.warning("k8s_api_error", status=response.status_code, path=path, body=response.text[:200])
                    return None
            except Exception as e:
                logger.error("k8s_api_exception", error=str(e), path=path)
                return None

    async def scale_deployment(self, name: str, namespace: str, replicas: int) -> bool:
        """Scale a deployment to the specified number of replicas."""
        path = f"/apis/apps/v1/namespaces/{namespace}/deployments/{name}"
        body = {"spec": {"replicas": replicas}}

        result = await self._k8s_api_call("PATCH", path, body)

        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "scale",
            "service": name,
            "namespace": namespace,
            "replicas": replicas,
            "success": result is not None,
            "phase": self.current_phase.value
        }
        self.activation_log.append(log_entry)

        if result:
            logger.info("deployment_scaled", name=name, namespace=namespace, replicas=replicas)
            return True
        else:
            logger.error("deployment_scale_failed", name=name, namespace=namespace)
            return False

    async def get_deployment_status(self, name: str, namespace: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a deployment."""
        path = f"/apis/apps/v1/namespaces/{namespace}/deployments/{name}"
        result = await self._k8s_api_call("GET", path)

        if result:
            return {
                "name": name,
                "namespace": namespace,
                "replicas": result.get("spec", {}).get("replicas", 0),
                "ready": result.get("status", {}).get("readyReplicas", 0),
                "available": result.get("status", {}).get("availableReplicas", 0)
            }
        return None

    async def activate_phase(self, phase: WorkflowPhase) -> Dict[str, Any]:
        """Activate all services required for a workflow phase."""
        self.current_phase = phase
        services = PHASE_SERVICES.get(phase, [])
        results = []

        logger.info("activating_phase", phase=phase.value, services=[s["name"] for s in services])

        for service in services:
            success = await self.scale_deployment(service["name"], service["namespace"], 1)
            results.append({
                "service": service["name"],
                "namespace": service["namespace"],
                "activated": success
            })

        # Wait for services to be ready
        await self._wait_for_services(services)

        return {
            "phase": phase.value,
            "services_activated": len([r for r in results if r["activated"]]),
            "services_failed": len([r for r in results if not r["activated"]]),
            "results": results
        }

    async def deactivate_phase(self, phase: WorkflowPhase) -> Dict[str, Any]:
        """Deactivate services that are only needed for a specific phase."""
        services = PHASE_SERVICES.get(phase, [])
        results = []

        # Don't deactivate core services
        core_names = {s["name"] for s in CORE_SERVICES}

        logger.info("deactivating_phase", phase=phase.value)

        for service in services:
            if service["name"] in core_names:
                logger.info("skipping_core_service", name=service["name"])
                continue

            # Check if service is needed by current or future phases
            if self._is_service_needed_later(service["name"]):
                logger.info("service_needed_later", name=service["name"])
                continue

            success = await self.scale_deployment(service["name"], service["namespace"], 0)
            results.append({
                "service": service["name"],
                "namespace": service["namespace"],
                "deactivated": success
            })

        return {
            "phase": phase.value,
            "services_deactivated": len([r for r in results if r["deactivated"]]),
            "results": results
        }

    def _is_service_needed_later(self, service_name: str) -> bool:
        """Check if a service is needed in upcoming phases."""
        phase_order = [WorkflowPhase.VIDEO, WorkflowPhase.ANALYZE, WorkflowPhase.IMPLEMENT, WorkflowPhase.WRITE]

        try:
            current_idx = phase_order.index(self.current_phase)
        except ValueError:
            return False

        for future_phase in phase_order[current_idx + 1:]:
            future_services = PHASE_SERVICES.get(future_phase, [])
            if any(s["name"] == service_name for s in future_services):
                return True

        return False

    async def _wait_for_services(self, services: List[Dict[str, str]], timeout: int = 120) -> bool:
        """Wait for services to become ready."""
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            all_ready = True

            for service in services:
                status = await self.get_deployment_status(service["name"], service["namespace"])
                if not status or status["ready"] < 1:
                    all_ready = False
                    break

            if all_ready:
                logger.info("all_services_ready", services=[s["name"] for s in services])
                return True

            await asyncio.sleep(5)

        logger.warning("services_not_ready_timeout", timeout=timeout)
        return False

    async def activate_core_services(self) -> Dict[str, Any]:
        """Activate all core services for school hours."""
        results = []

        logger.info("activating_core_services")

        for service in CORE_SERVICES:
            success = await self.scale_deployment(service["name"], service["namespace"], 1)
            results.append({
                "service": service["name"],
                "namespace": service["namespace"],
                "activated": success
            })

        await self._wait_for_services(CORE_SERVICES)

        return {
            "core_services_activated": len([r for r in results if r["activated"]]),
            "results": results
        }

    async def deactivate_all(self) -> Dict[str, Any]:
        """Deactivate all phase-specific services (end of school day)."""
        results = []
        core_names = {s["name"] for s in CORE_SERVICES}

        logger.info("deactivating_all_phase_services")

        all_phase_services = set()
        for services in PHASE_SERVICES.values():
            for service in services:
                if service["name"] not in core_names:
                    all_phase_services.add((service["name"], service["namespace"]))

        for name, namespace in all_phase_services:
            success = await self.scale_deployment(name, namespace, 0)
            results.append({
                "service": name,
                "namespace": namespace,
                "deactivated": success
            })

        return {
            "services_deactivated": len([r for r in results if r["deactivated"]]),
            "results": results
        }

    def get_activation_log(self) -> List[Dict[str, Any]]:
        """Get the full activation/deactivation log."""
        return self.activation_log

    async def get_phase_status(self) -> Dict[str, Any]:
        """Get current status of all phase services."""
        status = {
            "current_phase": self.current_phase.value,
            "phases": {}
        }

        for phase, services in PHASE_SERVICES.items():
            phase_status = []
            for service in services:
                svc_status = await self.get_deployment_status(service["name"], service["namespace"])
                phase_status.append(svc_status or {"name": service["name"], "status": "unknown"})
            status["phases"][phase.value] = phase_status

        return status


# Singleton instance
_controller: Optional[LayerController] = None


def get_layer_controller() -> LayerController:
    """Get or create the layer controller singleton."""
    global _controller
    if _controller is None:
        _controller = LayerController()
    return _controller
