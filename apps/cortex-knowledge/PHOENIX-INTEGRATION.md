# Phoenix LLM Observability Integration Guide

**Version**: 1.0.0
**Date**: 2026-01-12
**Status**: ACTIVE

---

## Overview

Phoenix (Arize AI) is deployed in the `cortex-knowledge` namespace to provide comprehensive LLM observability for all Claude API calls made by the Cortex agent framework.

**Access**: https://observability.ry-ops.dev

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│         Python Agent Framework                   │
│  (Master Agent + Worker Agents)                 │
│                                                  │
│  - Instrumented with Phoenix                    │
│  - Auto-traces all Claude API calls             │
│  - Sends OTLP traces to Phoenix                 │
└─────────────────────────────────────────────────┘
                     │
                     │ OTLP/gRPC (port 4317)
                     ▼
┌─────────────────────────────────────────────────┐
│              Phoenix Server                      │
│         (cortex-knowledge namespace)             │
│                                                  │
│  - Collector: Receives traces                   │
│  - UI: Dashboard (port 6006)                    │
│  - Storage: PostgreSQL (phoenix DB)             │
└─────────────────────────────────────────────────┘
                     │
                     │ Stores in
                     ▼
┌─────────────────────────────────────────────────┐
│          PostgreSQL Database                     │
│      (postgres.cortex-system.svc)               │
│                                                  │
│  Database: phoenix                              │
│  Tables: traces, spans, evaluations             │
└─────────────────────────────────────────────────┘
```

---

## Phase 2: Python Framework Integration

### Installation (in cortex-platform)

```bash
cd ~/Projects/cortex-platform
pip install arize-phoenix opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation
```

### Basic Instrumentation

#### 1. Configure Phoenix Tracer

Create `lib/observability/phoenix_tracer.py`:

```python
"""Phoenix observability integration for Cortex agents."""
import os
from phoenix.trace import using_project
from phoenix.otel import register
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Phoenix endpoint (k3s cluster)
PHOENIX_COLLECTOR_ENDPOINT = os.getenv(
    "PHOENIX_COLLECTOR_ENDPOINT",
    "http://phoenix.cortex-knowledge.svc.cluster.local:4317"
)

def initialize_phoenix():
    """Initialize Phoenix tracing for the entire application."""
    # Set up OTLP exporter
    exporter = OTLPSpanExporter(
        endpoint=PHOENIX_COLLECTOR_ENDPOINT,
        insecure=True  # Internal cluster traffic
    )

    # Register with Phoenix
    tracer_provider = register(
        project_name="cortex-agents",
        endpoint=PHOENIX_COLLECTOR_ENDPOINT
    )

    # Configure tracer
    trace.set_tracer_provider(tracer_provider)
    tracer_provider.add_span_processor(BatchSpanProcessor(exporter))

    return tracer_provider

# Initialize on import
initialize_phoenix()
```

#### 2. Instrument Master Agent

Update `services/agents/master_agent.py`:

```python
from lib.observability.phoenix_tracer import initialize_phoenix
from phoenix.trace import using_project
from anthropic import Anthropic
import asyncio

class MasterAgent:
    """Master orchestration agent with Phoenix observability."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = Anthropic(api_key=api_key)

    @using_project("cortex-agents")
    async def plan_task(self, user_request: str) -> dict:
        """Plan a task and delegate to workers.

        Phoenix automatically traces:
        - This function call
        - Claude API call below
        - Token usage, latency, cost
        """
        response = await self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": f"Plan this task: {user_request}"
                }
            ],
            metadata={
                "user_id": "system",
                "agent": "master",
                "task_type": "planning"
            }
        )

        return {
            "plan": response.content[0].text,
            "usage": response.usage,
            "model": response.model
        }

    @using_project("cortex-agents")
    async def delegate_to_worker(self, worker_name: str, task: dict):
        """Delegate task to a worker agent."""
        # Phoenix traces the delegation chain
        response = await self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=8192,
            messages=[
                {
                    "role": "user",
                    "content": f"Execute: {task['description']}"
                }
            ],
            metadata={
                "user_id": "system",
                "agent": f"worker-{worker_name}",
                "task_type": "execution",
                "parent_task": task.get("id")
            }
        )

        return response
```

#### 3. Instrument Worker Agents

Update `services/agents/worker_agent.py`:

```python
from lib.observability.phoenix_tracer import initialize_phoenix
from phoenix.trace import using_project, trace
from anthropic import Anthropic

class WorkerAgent:
    """Worker agent with Phoenix instrumentation."""

    def __init__(self, name: str, api_key: str, specialty: str):
        self.name = name
        self.specialty = specialty
        self.client = Anthropic(api_key=api_key)

    @using_project("cortex-agents")
    @trace(name="worker_execute_task")
    async def execute_task(self, task: dict) -> dict:
        """Execute a delegated task.

        Phoenix traces:
        - Worker identity (name, specialty)
        - Task execution time
        - Claude API calls
        - Success/failure
        - Cost per worker
        """
        with trace.get_current_span() as span:
            # Add worker metadata
            span.set_attribute("worker.name", self.name)
            span.set_attribute("worker.specialty", self.specialty)
            span.set_attribute("task.id", task.get("id", "unknown"))

            try:
                response = await self.client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=8192,
                    messages=[
                        {
                            "role": "user",
                            "content": task["prompt"]
                        }
                    ],
                    metadata={
                        "user_id": "system",
                        "agent": f"worker-{self.name}",
                        "specialty": self.specialty,
                        "task_id": task.get("id")
                    }
                )

                span.set_attribute("task.status", "success")
                span.set_attribute("task.tokens", response.usage.total_tokens)

                return {
                    "status": "success",
                    "result": response.content[0].text,
                    "usage": response.usage,
                    "worker": self.name
                }

            except Exception as e:
                span.set_attribute("task.status", "error")
                span.set_attribute("task.error", str(e))
                raise
```

#### 4. Environment Configuration

Add to `.env` in cortex-platform:

```bash
# Phoenix Observability
PHOENIX_COLLECTOR_ENDPOINT=http://phoenix.cortex-knowledge.svc.cluster.local:4317
PHOENIX_PROJECT_NAME=cortex-agents
PHOENIX_ENABLED=true
```

---

## Phase 3: Dashboard Configuration

### Dashboard Views to Create

#### 1. Agent Performance Dashboard

**Metrics to track**:
- Calls per minute (by agent type: master vs worker)
- Latency percentiles (p50, p95, p99)
- Success rate (% of calls without errors)
- Active agents (concurrent workers)
- Request queue depth

**Filters**:
- Time range (1h, 24h, 7d, 30d)
- Agent type (master, worker-coding, worker-analysis, etc.)
- Model (claude-sonnet-4-5, claude-opus-4-5)

**Visualizations**:
- Line chart: Calls/min over time
- Histogram: Latency distribution
- Bar chart: Top 10 slowest calls
- Gauge: Success rate

#### 2. Cost Tracking Dashboard

**Metrics to track**:
- Total tokens consumed (input + output)
- Cost per agent (based on Claude pricing)
- Cost per day (trend)
- Projected monthly cost
- Cost by model type
- Most expensive operations

**Calculations**:
```python
# Claude Sonnet 4.5 pricing (as of 2026-01-12)
INPUT_COST_PER_1M_TOKENS = 3.00   # $3 per 1M input tokens
OUTPUT_COST_PER_1M_TOKENS = 15.00 # $15 per 1M output tokens

total_cost = (
    (input_tokens / 1_000_000) * INPUT_COST_PER_1M_TOKENS +
    (output_tokens / 1_000_000) * OUTPUT_COST_PER_1M_TOKENS
)
```

**Visualizations**:
- Line chart: Daily cost trend
- Pie chart: Cost by agent type
- Table: Top 10 most expensive tasks
- Projection: Monthly cost forecast

#### 3. Error Analysis Dashboard

**Metrics to track**:
- Error rate (% of failed calls)
- Error types (API errors, timeouts, rate limits)
- Retry patterns (number of retries per call)
- Failed task chains (master → worker failures)
- Mean time to recovery (MTTR)

**Filters**:
- Error type
- Agent type
- Time range
- Severity

**Visualizations**:
- Line chart: Error rate over time
- Bar chart: Errors by type
- Table: Recent errors with stack traces
- Flow diagram: Failed task chains

#### 4. Chain Visualization Dashboard

**Metrics to track**:
- Task chains (master → worker flows)
- Chain depth (how many levels)
- Chain duration (total time)
- Parallel workers (concurrent executions)
- Bottlenecks (slowest step in chain)

**Visualizations**:
- Flamegraph: Task execution timeline
- Sankey diagram: Master → worker flows
- Tree view: Hierarchical task breakdown
- Waterfall: Sequential vs parallel execution

---

## Phase 4: Phoenix MCP Server (Future)

### Planned Capabilities

Create `services/mcp-servers/phoenix-mcp/server.py`:

```python
"""MCP server for Phoenix observability queries."""
from mcp.server import Server
from phoenix.client import PhoenixClient
import os

app = Server("phoenix-mcp")
phoenix = PhoenixClient(endpoint=os.getenv("PHOENIX_API_ENDPOINT"))

@app.tool()
async def query_metrics(
    agent_name: str = None,
    time_range: str = "1h",
    metric_type: str = "all"
) -> dict:
    """Query agent metrics from Phoenix.

    Args:
        agent_name: Filter by agent name (e.g., 'master', 'worker-coding')
        time_range: Time range (1h, 24h, 7d, 30d)
        metric_type: Type of metrics (latency, cost, errors, all)

    Returns:
        Dictionary with requested metrics
    """
    # Query Phoenix API
    metrics = await phoenix.query_metrics(
        agent=agent_name,
        time_range=time_range,
        metric_type=metric_type
    )

    return {
        "agent": agent_name or "all",
        "time_range": time_range,
        "metrics": metrics
    }

@app.tool()
async def get_traces(
    agent_name: str = None,
    status: str = "all",
    limit: int = 100
) -> list:
    """Retrieve traces from Phoenix.

    Args:
        agent_name: Filter by agent name
        status: Filter by status (success, error, all)
        limit: Maximum number of traces to return

    Returns:
        List of trace objects
    """
    traces = await phoenix.get_traces(
        agent=agent_name,
        status=status,
        limit=limit
    )

    return traces

@app.tool()
async def analyze_errors(
    time_range: str = "24h",
    agent_name: str = None
) -> dict:
    """Analyze errors over a time range.

    Args:
        time_range: Time range to analyze
        agent_name: Filter by agent name

    Returns:
        Error analysis summary
    """
    errors = await phoenix.analyze_errors(
        time_range=time_range,
        agent=agent_name
    )

    return {
        "time_range": time_range,
        "agent": agent_name or "all",
        "total_errors": errors["count"],
        "error_rate": errors["rate"],
        "top_errors": errors["top_types"],
        "recommendations": errors["recommendations"]
    }

@app.tool()
async def get_cost_summary(
    time_range: str = "30d",
    agent_name: str = None
) -> dict:
    """Get cost summary for agents.

    Args:
        time_range: Time range for cost analysis
        agent_name: Filter by agent name

    Returns:
        Cost summary with projections
    """
    costs = await phoenix.get_cost_summary(
        time_range=time_range,
        agent=agent_name
    )

    return {
        "time_range": time_range,
        "agent": agent_name or "all",
        "total_cost": costs["total"],
        "cost_by_model": costs["by_model"],
        "cost_by_agent": costs["by_agent"],
        "projected_monthly": costs["projection"]
    }
```

### MCP Server Configuration

Add to `cortex-platform/services/mcp-servers/phoenix-mcp/config.json`:

```json
{
  "mcpServers": {
    "phoenix": {
      "command": "python",
      "args": [
        "/app/services/mcp-servers/phoenix-mcp/server.py"
      ],
      "env": {
        "PHOENIX_API_ENDPOINT": "http://phoenix.cortex-knowledge.svc.cluster.local:6006"
      }
    }
  }
}
```

---

## Kubernetes Resources

### Endpoints

- **UI**: https://observability.ry-ops.dev
- **OTLP Collector**: `phoenix.cortex-knowledge.svc.cluster.local:4317`
- **Metrics**: `phoenix.cortex-knowledge.svc.cluster.local:9090`

### Database

- **Host**: `postgres.cortex-system.svc.cluster.local`
- **Port**: `5432`
- **Database**: `phoenix`
- **User**: `postgres`
- **Schema**: Auto-created by Phoenix on first run

### Resource Limits

```yaml
requests:
  cpu: 200m
  memory: 512Mi
limits:
  cpu: 1000m
  memory: 2Gi
```

---

## Verification

### 1. Check Deployment

```bash
kubectl get pods -n cortex-knowledge -l app=phoenix
kubectl logs -n cortex-knowledge -l app=phoenix
```

### 2. Verify Database Connection

```bash
# Connect to postgres and check phoenix database
kubectl exec -it -n cortex-system postgres-0 -- psql -U postgres -c "\l" | grep phoenix
```

### 3. Test OTLP Endpoint

```python
# From cortex-platform
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

exporter = OTLPSpanExporter(
    endpoint="http://phoenix.cortex-knowledge.svc.cluster.local:4317",
    insecure=True
)

# Should connect without errors
print(exporter)
```

### 4. Access UI

```bash
# Get ingress status
kubectl get ingress -n cortex-knowledge phoenix

# Access in browser
open https://observability.ry-ops.dev
```

---

## Next Steps

1. **Agent 2**: Implement Python agent framework with Phoenix instrumentation
2. **Integration**: Add Phoenix tracer to all Claude API calls
3. **Dashboards**: Configure the 4 dashboard views in Phoenix UI
4. **MCP Server**: Build Phoenix MCP server for programmatic queries
5. **Monitoring**: Set up alerts for high error rates, cost overruns

---

## References

- **Phoenix Docs**: https://docs.arize.com/phoenix
- **OTLP Specification**: https://opentelemetry.io/docs/specs/otlp/
- **Claude Pricing**: https://www.anthropic.com/pricing
- **GitOps Repo**: `~/Projects/cortex-gitops`
- **Platform Repo**: `~/Projects/cortex-platform`

---

**Status**: Ready for integration with Python agent framework
