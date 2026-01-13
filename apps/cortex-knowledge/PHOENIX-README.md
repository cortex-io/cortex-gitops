# Phoenix LLM Observability Platform

**Deployed**: 2026-01-12
**Namespace**: cortex-knowledge
**URL**: https://observability.ry-ops.dev
**Status**: Deployed via GitOps (ArgoCD auto-sync)

---

## Quick Start

### Access Phoenix UI
```bash
open https://observability.ry-ops.dev
```

### Verify Deployment
```bash
cd ~/Projects/cortex-gitops
./apps/cortex-knowledge/verify-phoenix.sh
```

### Check Status
```bash
kubectl get pods -n cortex-knowledge -l app=phoenix
kubectl logs -n cortex-knowledge -l app=phoenix
```

---

## What is Phoenix?

Phoenix (by Arize AI) is an open-source LLM observability platform that provides:

- **Trace Collection**: All Claude API calls from master and worker agents
- **Cost Tracking**: Token usage, pricing, daily/monthly projections
- **Performance Metrics**: Latency (p50/p95/p99), throughput, error rates
- **Error Analysis**: Failed calls, retry patterns, debugging
- **Chain Visualization**: Master → worker task flows

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│         Python Agent Framework                   │
│  (Master Agent + Worker Agents)                 │
│                                                  │
│  Instrumented with Phoenix OpenTelemetry        │
└─────────────────────────────────────────────────┘
                     │
                     │ OTLP/gRPC Traces
                     ▼
┌─────────────────────────────────────────────────┐
│           Phoenix Server                         │
│     phoenix.cortex-knowledge.svc:4317           │
│                                                  │
│  - Collector: Receives traces (OTLP)            │
│  - UI: Dashboard (port 6006)                    │
│  - Metrics: Prometheus (port 9090)              │
└─────────────────────────────────────────────────┘
                     │
                     │ Stores Traces
                     ▼
┌─────────────────────────────────────────────────┐
│        PostgreSQL Database                       │
│  postgres.cortex-system.svc:5432/phoenix        │
│                                                  │
│  Tables: traces, spans, evaluations             │
└─────────────────────────────────────────────────┘
```

---

## Files in this Directory

| File | Purpose |
|------|---------|
| `phoenix-deployment.yaml` | Phoenix server deployment (collector + UI) |
| `phoenix-service.yaml` | ClusterIP service (ports 6006, 4317, 9090) |
| `phoenix-ingress.yaml` | External access at observability.ry-ops.dev |
| `phoenix-db-init-job.yaml` | PostgreSQL database initialization |
| `PHOENIX-INTEGRATION.md` | Comprehensive integration guide for Python framework |
| `PHOENIX-DEPLOYMENT-SUMMARY.md` | Deployment status and verification procedures |
| `verify-phoenix.sh` | Automated verification script |
| `PHOENIX-README.md` | This file |

---

## Endpoints

### Web UI
- **External**: https://observability.ry-ops.dev
- **Internal**: http://phoenix.cortex-knowledge.svc.cluster.local:6006

### OTLP Collector (for agents)
- **Endpoint**: http://phoenix.cortex-knowledge.svc.cluster.local:4317
- **Protocol**: gRPC (OTLP)
- **Purpose**: Receive traces from instrumented Python agents

### Prometheus Metrics
- **Endpoint**: http://phoenix.cortex-knowledge.svc.cluster.local:9090
- **Purpose**: Scrape Phoenix internal metrics

---

## Database

### Connection Details
- **Host**: postgres.cortex-system.svc.cluster.local
- **Port**: 5432
- **Database**: phoenix
- **User**: postgres
- **Password**: postgres

### Schema
Phoenix automatically creates tables on first run:
- `traces`: Top-level trace records
- `spans`: Individual span records (one per API call)
- `evaluations`: Evaluation results (if configured)

### Verify Database
```bash
kubectl exec -it -n cortex-system postgres-0 -- psql -U postgres -c "\l" | grep phoenix
kubectl exec -it -n cortex-system postgres-0 -- psql -U postgres phoenix -c "\dt"
```

---

## Integration with Python Agent Framework

### For Agent 2: Implementation Checklist

- [ ] Install Phoenix Python packages
  ```bash
  cd ~/Projects/cortex-platform
  pip install arize-phoenix opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation
  ```

- [ ] Create tracer initialization module
  - Location: `lib/observability/phoenix_tracer.py`
  - See: `PHOENIX-INTEGRATION.md` → "Phase 2: Python Framework Integration"

- [ ] Instrument Master Agent
  - Add `@using_project("cortex-agents")` decorator
  - Configure OTLP endpoint
  - Include metadata (agent name, task ID, model)

- [ ] Instrument Worker Agents
  - Add `@trace()` decorator to task execution
  - Include worker identity (name, specialty)
  - Track success/failure status

- [ ] Configure Environment Variables
  ```bash
  export PHOENIX_COLLECTOR_ENDPOINT=http://phoenix.cortex-knowledge.svc.cluster.local:4317
  export PHOENIX_PROJECT_NAME=cortex-agents
  export PHOENIX_ENABLED=true
  ```

- [ ] Test Trace Collection
  - Run a simple master → worker task
  - Verify traces appear in Phoenix UI
  - Check trace metadata is correct

### Example: Instrumented Agent

```python
from phoenix.trace import using_project
from anthropic import Anthropic

class MasterAgent:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)

    @using_project("cortex-agents")
    async def plan_task(self, user_request: str):
        # Phoenix automatically traces this Claude API call
        response = await self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            messages=[{"role": "user", "content": user_request}],
            metadata={
                "agent": "master",
                "task_type": "planning"
            }
        )
        return response
```

Full examples in `PHOENIX-INTEGRATION.md`.

---

## Dashboard Configuration (Phase 3)

After agents start sending traces, configure these dashboards in Phoenix UI:

### 1. Agent Performance Dashboard
- **Metrics**: Calls/min, latency (p50/p95/p99), success rate
- **Filters**: Agent type, time range, model
- **Purpose**: Monitor agent health and performance

### 2. Cost Tracking Dashboard
- **Metrics**: Tokens consumed, cost per agent, daily trend, monthly projection
- **Calculations**: Input tokens × $3/1M + Output tokens × $15/1M
- **Purpose**: Budget tracking and optimization

### 3. Error Analysis Dashboard
- **Metrics**: Error rate, error types, retry patterns, MTTR
- **Filters**: Error type, agent, severity
- **Purpose**: Debug failed calls and improve reliability

### 4. Chain Visualization Dashboard
- **Metrics**: Task chains, chain depth, duration, bottlenecks
- **Visualizations**: Flamegraph, Sankey diagram, waterfall
- **Purpose**: Optimize task delegation and parallelization

Detailed configuration instructions in `PHOENIX-INTEGRATION.md`.

---

## MCP Server (Phase 4 - Future)

Plan for `phoenix-mcp-server` to provide programmatic access:

### Planned Tools
- `query_metrics(agent_name, time_range)` → agent metrics
- `get_traces(filter)` → trace records
- `analyze_errors(time_range)` → error summary
- `get_cost_summary(time_range)` → cost breakdown

### Use Cases
- Automated cost alerts
- Performance regression detection
- Error rate monitoring
- Daily reports

Full design in `PHOENIX-INTEGRATION.md` → "Phase 4: Phoenix MCP Server".

---

## Verification Procedures

### 1. Check Deployment
```bash
kubectl get deployment phoenix -n cortex-knowledge
kubectl get pods -n cortex-knowledge -l app=phoenix
```

### 2. Check Service
```bash
kubectl get service phoenix -n cortex-knowledge
kubectl describe service phoenix -n cortex-knowledge
```

### 3. Check Ingress
```bash
kubectl get ingress phoenix -n cortex-knowledge
curl -I https://observability.ry-ops.dev
```

### 4. Check Database
```bash
kubectl exec -it -n cortex-system postgres-0 -- \
  psql -U postgres -c "SELECT datname FROM pg_database WHERE datname='phoenix';"
```

### 5. Check Logs
```bash
kubectl logs -n cortex-knowledge -l app=phoenix --tail=50
```

### 6. Test OTLP Endpoint
```bash
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl -v telnet://phoenix.cortex-knowledge.svc.cluster.local:4317
```

### 7. Run Automated Verification
```bash
./apps/cortex-knowledge/verify-phoenix.sh
```

---

## Troubleshooting

### Phoenix Pod Not Starting

**Symptoms**: Pod stuck in `Pending` or `CrashLoopBackOff`

**Diagnosis**:
```bash
kubectl describe pod -n cortex-knowledge -l app=phoenix
kubectl logs -n cortex-knowledge -l app=phoenix
```

**Common Causes**:
- Database connection failure (check postgres.cortex-system.svc.cluster.local:5432)
- Resource limits too low (increase memory/CPU)
- Image pull failure (check image: arizephoenix/phoenix:latest)

### Ingress Not Accessible

**Symptoms**: observability.ry-ops.dev returns 404 or connection refused

**Diagnosis**:
```bash
kubectl describe ingress phoenix -n cortex-knowledge
kubectl get certificate phoenix-tls -n cortex-knowledge
```

**Common Causes**:
- DNS not propagated (wait 5-10 minutes)
- TLS certificate provisioning (check cert-manager logs)
- Ingress controller not routing (check nginx-ingress logs)

### Database Connection Issues

**Symptoms**: Phoenix logs show PostgreSQL connection errors

**Diagnosis**:
```bash
kubectl exec -n cortex-knowledge <phoenix-pod> -- \
  nc -zv postgres.cortex-system.svc.cluster.local 5432
```

**Common Causes**:
- PostgreSQL not running (check postgres pods in cortex-system)
- Database 'phoenix' not created (re-run phoenix-db-init-job)
- Wrong credentials (verify PHOENIX_SQL_DATABASE_URL env var)

### Traces Not Appearing

**Symptoms**: Python agents running, but no traces in Phoenix UI

**Diagnosis**:
```bash
# Check Phoenix logs for incoming traces
kubectl logs -n cortex-knowledge -l app=phoenix | grep -i "trace"

# Test from agent pod
kubectl exec -it <agent-pod> -- \
  nc -zv phoenix.cortex-knowledge.svc.cluster.local 4317
```

**Common Causes**:
- OTLP endpoint misconfigured in agent code
- Phoenix tracer not initialized
- Firewall blocking port 4317 (check NetworkPolicies)
- Metadata missing from API calls

---

## GitOps Management

### Making Changes

All changes go through Git → ArgoCD → Cluster:

```bash
cd ~/Projects/cortex-gitops

# Edit manifests
vim apps/cortex-knowledge/phoenix-deployment.yaml

# Commit and push
git add apps/cortex-knowledge/phoenix-deployment.yaml
git commit -m "Update Phoenix configuration"
git push origin main

# ArgoCD auto-syncs within 3 minutes
kubectl get application cortex-knowledge -n argocd
```

### Rollback

```bash
cd ~/Projects/cortex-gitops
git log --oneline  # Find commit to revert
git revert <commit-hash>
git push origin main
# ArgoCD auto-syncs the rollback
```

### Force Sync

```bash
kubectl patch application cortex-knowledge -n argocd \
  --type merge \
  -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
```

---

## Success Criteria

### Phase 1: Deployment (Complete)
- [x] Phoenix deployment manifest created
- [x] Service exposing UI, OTLP, metrics
- [x] Ingress at observability.ry-ops.dev
- [x] Database initialization job
- [x] Integration guide documented
- [x] Manifests committed to Git
- [x] Pushed to GitHub

### Phase 2: Integration (Agent 2)
- [ ] Phoenix Python packages installed in cortex-platform
- [ ] Tracer initialization module created
- [ ] Master agent instrumented
- [ ] Worker agents instrumented
- [ ] Traces appearing in Phoenix UI

### Phase 3: Dashboards
- [ ] Agent performance dashboard configured
- [ ] Cost tracking dashboard configured
- [ ] Error analysis dashboard configured
- [ ] Chain visualization dashboard configured

### Phase 4: MCP Server (Future)
- [ ] phoenix-mcp-server designed
- [ ] MCP server implemented
- [ ] Tools: query_metrics, get_traces, analyze_errors, get_cost_summary
- [ ] Deployed to cortex-knowledge namespace

---

## Resources

### Documentation
- **Integration Guide**: `PHOENIX-INTEGRATION.md` (comprehensive)
- **Deployment Summary**: `PHOENIX-DEPLOYMENT-SUMMARY.md` (status)
- **This README**: `PHOENIX-README.md` (quick reference)

### Scripts
- **Verification**: `verify-phoenix.sh` (automated checks)

### External Links
- **Phoenix Docs**: https://docs.arize.com/phoenix
- **Phoenix GitHub**: https://github.com/Arize-ai/phoenix
- **OpenTelemetry**: https://opentelemetry.io/docs/
- **OTLP Specification**: https://opentelemetry.io/docs/specs/otlp/
- **Claude Pricing**: https://www.anthropic.com/pricing

### Repositories
- **GitOps**: https://github.com/ry-ops/cortex-gitops
- **Platform**: https://github.com/ry-ops/cortex-platform

---

## Support

### For Deployment Issues
- Check: `PHOENIX-DEPLOYMENT-SUMMARY.md` → "Troubleshooting"
- Run: `./verify-phoenix.sh`
- Logs: `kubectl logs -n cortex-knowledge -l app=phoenix`

### For Integration Issues
- Check: `PHOENIX-INTEGRATION.md` → "Phase 2: Python Framework Integration"
- Example: `PHOENIX-INTEGRATION.md` → "Basic Instrumentation"
- Test: Verify OTLP endpoint is reachable from agent pods

### For Dashboard Configuration
- Check: `PHOENIX-INTEGRATION.md` → "Phase 3: Dashboard Configuration"
- Reference: Phoenix UI documentation
- Examples: Pre-configured dashboard templates

---

**Status**: Phase 1 Complete - Ready for Agent 2 Integration
**Next**: Implement Python agent framework with Phoenix tracing
**Owner**: Agent 2 (Python Framework Development)
