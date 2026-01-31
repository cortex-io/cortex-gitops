#!/usr/bin/env python3
"""
Workflow Orchestrator - Autonomous learning workflow for Cortex School

Manages the complete learning cycle:
1. VIDEO: Watch and process YouTube content
2. ANALYZE: Extract insights and identify improvements
3. IMPLEMENT: Create and deploy changes
4. WRITE: Document and blog about the learning

Each phase activates only the services it needs.

Enhanced with memory-service integration for:
- Persistent workflow state across restarts
- Learning history tracking
- Error recovery and workflow resumption
"""
import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum

import httpx
import structlog

from layer_controller import LayerController, WorkflowPhase, get_layer_controller

logger = structlog.get_logger()

# Service URLs
YOUTUBE_CHANNEL_MCP = os.getenv("YOUTUBE_CHANNEL_MCP_URL", "http://youtube-channel-mcp.cortex.svc.cluster.local:8080")
YOUTUBE_INGESTION_MCP = os.getenv("YOUTUBE_INGESTION_MCP_URL", "http://youtube-ingestion-mcp.cortex.svc.cluster.local:8080")
GITHUB_MCP = os.getenv("GITHUB_MCP_URL", "http://github-mcp-server.cortex-system.svc.cluster.local:3002")
KUBERNETES_MCP = os.getenv("KUBERNETES_MCP_URL", "http://kubernetes-mcp-server.cortex-system.svc.cluster.local:3001")
BLOG_WRITER_URL = os.getenv("BLOG_WRITER_URL", "http://blog-writer.cortex-school.svc.cluster.local:8080")
RAG_VALIDATOR_URL = os.getenv("RAG_VALIDATOR_URL", "http://rag-validator.cortex-school.svc.cluster.local:8080")
CORTEX_MCP = os.getenv("CORTEX_MCP_URL", "http://cortex-mcp-server.cortex-system.svc.cluster.local:3000")
MEMORY_SERVICE_URL = os.getenv("MEMORY_SERVICE_URL", "http://memory-service.cortex-system.svc.cluster.local:8080")


class WorkflowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MemoryClient:
    """Client for memory-service integration."""

    def __init__(self, base_url: str = MEMORY_SERVICE_URL):
        self.base_url = base_url
        self.session_id: Optional[str] = None

    async def create_session(self, task: str, metadata: Dict = None) -> Optional[str]:
        """Create a new memory session for this workflow."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/memory/sessions",
                    json={
                        "current_task": task,
                        "working_directory": "/cortex-school",
                        "metadata": metadata or {}
                    }
                )
                if response.status_code in [200, 201]:
                    data = response.json()
                    self.session_id = data.get("session_id")
                    logger.info("memory_session_created", session_id=self.session_id)
                    return self.session_id
            except Exception as e:
                logger.warning("memory_service_unavailable", error=str(e))
        return None

    async def record_decision(self, decision: str, rationale: str = None) -> bool:
        """Record a workflow decision."""
        if not self.session_id:
            return False
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/memory/sessions/{self.session_id}/decision",
                    params={"decision": decision, "rationale": rationale}
                )
                return response.status_code == 200
            except Exception:
                return False

    async def record_action(self, action_type: str, description: str, details: Dict = None, result: str = None) -> bool:
        """Record a workflow action."""
        if not self.session_id:
            return False
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/memory/sessions/{self.session_id}/action",
                    params={
                        "action_type": action_type,
                        "description": description,
                        "result": result
                    },
                    json=details
                )
                return response.status_code == 200
            except Exception:
                return False

    async def record_timeline_event(self, event_type: str, description: str, details: Dict = None) -> bool:
        """Record a timeline event for correlation."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/memory/timeline/event",
                    json={
                        "event_type": event_type,
                        "source": "school-orchestrator",
                        "description": description,
                        "details": details or {},
                        "affected_components": ["cortex-school", "school-activator"]
                    }
                )
                return response.status_code == 200
            except Exception:
                return False

    async def update_session(self, current_task: str = None, metadata: Dict = None) -> bool:
        """Update session state."""
        if not self.session_id:
            return False
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                update_data = {}
                if current_task:
                    update_data["current_task"] = current_task
                if metadata:
                    update_data["metadata"] = metadata
                response = await client.put(
                    f"{self.base_url}/memory/sessions/{self.session_id}",
                    json=update_data
                )
                return response.status_code == 200
            except Exception:
                return False

    async def end_session(self, summary: str) -> bool:
        """End the memory session."""
        if not self.session_id:
            return False
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/memory/sessions/{self.session_id}/end",
                    params={"summary": summary}
                )
                return response.status_code == 200
            except Exception:
                return False


class WorkflowOrchestrator:
    """Orchestrates the complete learning workflow with memory persistence."""

    def __init__(self):
        self.layer_controller = get_layer_controller()
        self.memory = MemoryClient()
        self.workflow_log: List[Dict[str, Any]] = []
        self.current_workflow: Optional[Dict[str, Any]] = None

    async def _log(self, phase: str, step: str, status: str, details: Any = None):
        """Log a workflow event and persist to memory."""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "phase": phase,
            "step": step,
            "status": status,
            "details": details
        }
        self.workflow_log.append(entry)
        logger.info("workflow_event", **entry)

        # Persist to memory service
        await self.memory.record_action(
            action_type=f"workflow_{phase}",
            description=f"{phase}/{step}: {status}",
            details={"step": step, "status": status, "details": details},
            result="success" if status == "completed" else status
        )

    async def _call_mcp(self, url: str, method: str, params: Dict = None) -> Optional[Dict]:
        """Call an MCP server."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    url,
                    json={
                        "jsonrpc": "2.0",
                        "method": method,
                        "params": params or {},
                        "id": 1
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("result")
                else:
                    logger.error("mcp_call_failed", url=url, status=response.status_code)
                    return None
            except Exception as e:
                logger.error("mcp_call_exception", url=url, error=str(e))
                return None

    async def _call_service(self, url: str, endpoint: str, method: str = "POST", data: Dict = None) -> Optional[Dict]:
        """Call a REST service."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                full_url = f"{url}{endpoint}"
                if method == "GET":
                    response = await client.get(full_url, params=data)
                else:
                    response = await client.post(full_url, json=data)

                if response.status_code in [200, 201]:
                    return response.json()
                else:
                    logger.error("service_call_failed", url=full_url, status=response.status_code)
                    return None
            except Exception as e:
                logger.error("service_call_exception", url=url, error=str(e))
                return None

    # =========================================================================
    # PHASE 1: VIDEO - Watch and process YouTube content
    # =========================================================================
    async def phase_video(self, video_url: str) -> Dict[str, Any]:
        """Process a YouTube video."""
        await self._log("video", "start", "running", {"video_url": video_url})

        # Activate video phase services
        activation = await self.layer_controller.activate_phase(WorkflowPhase.VIDEO)
        await self._log("video", "activate_services", "completed", activation)

        # Wait for services to be ready
        await asyncio.sleep(10)

        # Extract video ID
        video_id = self._extract_video_id(video_url)
        if not video_id:
            await self._log("video", "extract_id", "failed", {"error": "Could not extract video ID"})
            return {"success": False, "error": "Invalid video URL"}

        await self._log("video", "extract_id", "completed", {"video_id": video_id})

        # Fetch video metadata
        metadata = await self._call_mcp(
            YOUTUBE_CHANNEL_MCP,
            "tools/call",
            {"name": "get_video_details", "arguments": {"video_id": video_id}}
        )
        await self._log("video", "fetch_metadata", "completed" if metadata else "failed", metadata)

        # Fetch transcript
        transcript = await self._call_mcp(
            YOUTUBE_INGESTION_MCP,
            "tools/call",
            {"name": "get_transcript", "arguments": {"video_id": video_id}}
        )
        await self._log("video", "fetch_transcript", "completed" if transcript else "failed",
                  {"length": len(str(transcript)) if transcript else 0})

        return {
            "success": True,
            "video_id": video_id,
            "metadata": metadata,
            "transcript": transcript,
            "phase": "video"
        }

    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
        import re
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    # =========================================================================
    # PHASE 2: ANALYZE - Extract insights and identify improvements
    # =========================================================================
    async def phase_analyze(self, video_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze video content for improvement opportunities."""
        await self._log("analyze", "start", "running")

        # Activate analyze phase (may already have some services from video phase)
        activation = await self.layer_controller.activate_phase(WorkflowPhase.ANALYZE)
        await self._log("analyze", "activate_services", "completed", activation)

        # Use Cortex MCP to analyze content
        analysis = await self._call_mcp(
            CORTEX_MCP,
            "tools/call",
            {
                "name": "analyze_content",
                "arguments": {
                    "content": json.dumps({
                        "title": video_data.get("metadata", {}).get("title", "Unknown"),
                        "transcript": video_data.get("transcript", ""),
                        "context": "Analyze this video content for improvements applicable to our Cortex infrastructure"
                    })
                }
            }
        )
        await self._log("analyze", "content_analysis", "completed" if analysis else "failed", analysis)

        # Identify actionable improvements
        improvements = self._extract_improvements(analysis, video_data)
        await self._log("analyze", "extract_improvements", "completed", {"count": len(improvements)})

        return {
            "success": True,
            "analysis": analysis,
            "improvements": improvements,
            "phase": "analyze"
        }

    def _extract_improvements(self, analysis: Any, video_data: Dict) -> List[Dict[str, Any]]:
        """Extract actionable improvements from analysis."""
        # This would typically use Claude to identify improvements
        # For now, return placeholder structure
        return [{
            "id": "imp-001",
            "title": f"Improvement from: {video_data.get('metadata', {}).get('title', 'Video')}",
            "description": "Identified improvement opportunity",
            "priority": "medium",
            "estimated_effort": "low",
            "target_component": "cortex-system"
        }]

    # =========================================================================
    # PHASE 3: IMPLEMENT - Create and deploy changes
    # =========================================================================
    async def phase_implement(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Implement identified improvements."""
        await self._log("implement", "start", "running")

        # Activate implementation phase services
        activation = await self.layer_controller.activate_phase(WorkflowPhase.IMPLEMENT)
        await self._log("implement", "activate_services", "completed", activation)

        improvements = analysis_data.get("improvements", [])
        implemented = []

        for improvement in improvements:
            await self._log("implement", "processing", "running", {"improvement": improvement["id"]})

            # Create branch for changes
            branch_name = f"school/auto-{improvement['id']}-{datetime.utcnow().strftime('%Y%m%d')}"
            branch_result = await self._call_mcp(
                GITHUB_MCP,
                "tools/call",
                {
                    "name": "create_branch",
                    "arguments": {
                        "repo": "ry-ops/cortex-gitops",
                        "branch": branch_name,
                        "from_branch": "main"
                    }
                }
            )
            await self._log("implement", "create_branch", "completed" if branch_result else "skipped",
                      {"branch": branch_name})

            # Note: Actual implementation would involve:
            # 1. Generating code changes
            # 2. Creating commits
            # 3. Running tests
            # 4. Creating PR

            implemented.append({
                "improvement_id": improvement["id"],
                "branch": branch_name,
                "status": "implemented" if branch_result else "skipped"
            })

        return {
            "success": True,
            "implemented": implemented,
            "phase": "implement"
        }

    # =========================================================================
    # PHASE 4: WRITE - Document and blog about the learning
    # =========================================================================
    async def phase_write(self, video_data: Dict, analysis_data: Dict, implementation_data: Dict) -> Dict[str, Any]:
        """Write documentation and blog post about the learning."""
        await self._log("write", "start", "running")

        # Activate write phase services
        activation = await self.layer_controller.activate_phase(WorkflowPhase.WRITE)
        await self._log("write", "activate_services", "completed", activation)

        # Generate blog post
        blog_content = await self._call_service(
            BLOG_WRITER_URL,
            "/api/blog/generate",
            data={
                "topic": f"Learning from: {video_data.get('metadata', {}).get('title', 'Video')}",
                "source_content": {
                    "video": video_data,
                    "analysis": analysis_data,
                    "implementation": implementation_data
                },
                "style": "technical",
                "length": "medium"
            }
        )
        await self._log("write", "generate_blog", "completed" if blog_content else "failed", blog_content)

        # Validate content
        if blog_content:
            validation = await self._call_service(
                RAG_VALIDATOR_URL,
                "/api/validate",
                data={
                    "content": blog_content.get("content", ""),
                    "sources": [video_data.get("video_id")]
                }
            )
            await self._log("write", "validate_content", "completed" if validation else "failed", validation)
        else:
            validation = None

        return {
            "success": blog_content is not None,
            "blog_content": blog_content,
            "validation": validation,
            "phase": "write"
        }

    # =========================================================================
    # MAIN WORKFLOW
    # =========================================================================
    async def run_workflow(self, video_url: str) -> Dict[str, Any]:
        """Run the complete learning workflow for a video with memory persistence."""
        workflow_id = f"wf-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

        self.current_workflow = {
            "id": workflow_id,
            "video_url": video_url,
            "started_at": datetime.utcnow().isoformat() + "Z",
            "status": WorkflowStatus.RUNNING.value,
            "phases": {}
        }

        # Create memory session for this workflow
        await self.memory.create_session(
            task=f"Learning workflow: {video_url}",
            metadata={
                "workflow_id": workflow_id,
                "video_url": video_url,
                "workflow_type": "school_learning"
            }
        )

        await self._log("workflow", "start", "running", {"workflow_id": workflow_id, "video_url": video_url})

        # Record workflow start in timeline for correlation
        await self.memory.record_timeline_event(
            event_type="action",
            description=f"School workflow started: {workflow_id}",
            details={"video_url": video_url, "workflow_id": workflow_id}
        )

        try:
            # Activate core services first
            core_activation = await self.layer_controller.activate_core_services()
            await self._log("workflow", "activate_core", "completed", core_activation)

            # PHASE 1: VIDEO
            await self.memory.update_session(current_task="Phase 1: Processing video")
            video_result = await self.phase_video(video_url)
            self.current_workflow["phases"]["video"] = video_result
            if not video_result.get("success"):
                raise Exception("Video phase failed")

            # Record decision point
            await self.memory.record_decision(
                decision=f"Video processed successfully: {video_result.get('metadata', {}).get('title', 'Unknown')}",
                rationale="Transcript and metadata extracted, proceeding to analysis"
            )

            # PHASE 2: ANALYZE
            await self.memory.update_session(current_task="Phase 2: Analyzing content")
            analysis_result = await self.phase_analyze(video_result)
            self.current_workflow["phases"]["analyze"] = analysis_result

            # Record analysis decision
            improvements = analysis_result.get("improvements", [])
            await self.memory.record_decision(
                decision=f"Identified {len(improvements)} improvement opportunities",
                rationale="Analysis complete, moving to implementation phase"
            )

            # PHASE 3: IMPLEMENT
            await self.memory.update_session(current_task="Phase 3: Implementing changes")
            implementation_result = await self.phase_implement(analysis_result)
            self.current_workflow["phases"]["implement"] = implementation_result

            # PHASE 4: WRITE
            await self.memory.update_session(current_task="Phase 4: Writing documentation")
            write_result = await self.phase_write(video_result, analysis_result, implementation_result)
            self.current_workflow["phases"]["write"] = write_result

            # Complete
            self.current_workflow["status"] = WorkflowStatus.COMPLETED.value
            self.current_workflow["completed_at"] = datetime.utcnow().isoformat() + "Z"
            await self._log("workflow", "complete", "completed", {"workflow_id": workflow_id})

            # End memory session with summary
            video_title = video_result.get("metadata", {}).get("title", "Video")
            await self.memory.end_session(
                summary=f"Completed learning workflow for '{video_title}'. "
                        f"Processed {len(improvements)} improvements. "
                        f"Blog content {'generated' if write_result.get('success') else 'not generated'}."
            )

        except Exception as e:
            self.current_workflow["status"] = WorkflowStatus.FAILED.value
            self.current_workflow["error"] = str(e)
            await self._log("workflow", "error", "failed", {"error": str(e)})

            # Record failure in timeline
            await self.memory.record_timeline_event(
                event_type="error",
                description=f"School workflow failed: {workflow_id}",
                details={"error": str(e), "workflow_id": workflow_id}
            )

            # End session with error summary
            await self.memory.end_session(summary=f"Workflow failed: {str(e)}")

        finally:
            # Deactivate phase-specific services
            await self.layer_controller.deactivate_all()
            await self._log("workflow", "cleanup", "completed")

        return self.current_workflow

    def get_workflow_log(self) -> List[Dict[str, Any]]:
        """Get the complete workflow log."""
        return self.workflow_log

    def get_layer_log(self) -> List[Dict[str, Any]]:
        """Get the layer activation log."""
        return self.layer_controller.get_activation_log()


# Singleton instance
_orchestrator: Optional[WorkflowOrchestrator] = None


def get_orchestrator() -> WorkflowOrchestrator:
    """Get or create the orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = WorkflowOrchestrator()
    return _orchestrator
