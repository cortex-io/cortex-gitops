# Phoenix LLM Observability - Deployment Summary

**Date**: 2026-01-12
**Status**: Deployed (waiting for ArgoCD sync)
**Namespace**: cortex-knowledge
**URL**: https://observability.ry-ops.dev

---

## What Was Deployed

### 1. Phoenix Server (phoenix-deployment.yaml)
- **Image**: arizephoenix/phoenix:latest
- **Replicas**: 1
- **Resources**: 200m-1000m CPU, 512Mi-2Gi memory
- **Ports**:
  - 6006: Web UI (http)
  - 4317: OTLP gRPC collector (for traces)
  - 9090: Prometheus metrics
- **Storage**: ephemeral (emptyDir) for /data and /tmp
- **Security**: runAsNonRoot, seccompProfile, capabilities dropped

### 2. Phoenix Service (phoenix-service.yaml)
- **Type**: ClusterIP
- **Selector**: app=phoenix
- **Ports**:
  - http: 6006 → 6006 (UI)
  - otlp-grpc: 4317 → 4317 (traces)
  - metrics: 9090 → 9090 (Prometheus)

### 3. Phoenix Ingress (phoenix-ingress.yaml)
- **Host**: observability.ry-ops.dev
- **TLS**: Let's Encrypt (cert-manager)
- **Class**: nginx
- **Backend**: phoenix:6006

### 4. Database Initialization Job (phoenix-db-init-job.yaml)
- **Purpose**: Create 'phoenix' database in PostgreSQL
- **Image**: postgres:15-alpine
- **Target**: postgres.cortex-system.svc.cluster.local:5432
- **TTL**: 86400 seconds (24 hours cleanup)

### 5. Integration Guide (PHOENIX-INTEGRATION.md)
- **Purpose**: Comprehensive integration documentation
- **Sections**:
  - Architecture overview
  - Python framework instrumentation examples
  - Dashboard configuration guide
  - Future MCP server design
  - Verification procedures

---

## Database Configuration

- **Host**: postgres.cortex-system.svc.cluster.local
- **Port**: 5432
- **Database**: phoenix (auto-created by init job)
- **User**: postgres
- **Password**: postgres (from existing deployment)
- **Connection String**: `postgresql://postgres:postgres@postgres.cortex-system.svc.cluster.local:5432/phoenix`

---

## Architecture Flow

```
Python Agents → OTLP (4317) → Phoenix → PostgreSQL
                                 ↓
                          Web UI (6006)
                                 ↓
                      observability.ry-ops.dev
```

---

## GitOps Deployment Status

### Commit Details
- **Commit**: fc13ec5
- **Branch**: main
- **Repository**: github.com/ry-ops/cortex-gitops
- **Files Changed**: 5 (4 manifests + 1 doc)
- **Lines Added**: 790+

### ArgoCD Status
- **Application**: cortex-knowledge
- **Status**: OutOfSync (detected new manifests)
- **Auto-sync**: Enabled (will sync within 3 minutes)
- **Self-heal**: Enabled
- **Prune**: Enabled

### Expected Resources After Sync
- 1 Deployment (phoenix)
- 1 Service (phoenix)
- 1 Ingress (phoenix)
- 1 Job (phoenix-db-init)

---

## Verification Commands

### Check ArgoCD Sync Status
```bash
kubectl get application cortex-knowledge -n argocd
kubectl describe application cortex-knowledge -n argocd
```

### Check Phoenix Deployment
```bash
kubectl get pods -n cortex-knowledge -l app=phoenix
kubectl logs -n cortex-knowledge -l app=phoenix
kubectl get service -n cortex-knowledge phoenix
kubectl get ingress -n cortex-knowledge phoenix
```

### Check Database Initialization
```bash
kubectl get jobs -n cortex-knowledge phoenix-db-init
kubectl logs -n cortex-knowledge job/phoenix-db-init
```

### Verify Database
```bash
# Connect to PostgreSQL
kubectl exec -it -n cortex-system postgres-0 -- psql -U postgres

# In psql:
\l                    # List databases (should see 'phoenix')
\c phoenix            # Connect to phoenix database
\dt                   # List tables (Phoenix will create on first run)
```

### Test Phoenix UI
```bash
# Get ingress status
kubectl get ingress -n cortex-knowledge phoenix

# Access in browser
open https://observability.ry-ops.dev
```

### Test OTLP Endpoint
```bash
# From inside cluster
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl -v telnet://phoenix.cortex-knowledge.svc.cluster.local:4317
```

---

## Integration Readiness

### For Agent 2 (Python Framework Development)

1. **Installation Requirements**:
   ```bash
   pip install arize-phoenix opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation
   ```

2. **Environment Variables**:
   ```bash
   export PHOENIX_COLLECTOR_ENDPOINT=http://phoenix.cortex-knowledge.svc.cluster.local:4317
   export PHOENIX_PROJECT_NAME=cortex-agents
   ```

3. **Code Integration Points**:
   - Master agent: Wrap task planning and delegation
   - Worker agents: Wrap task execution
   - Claude API calls: Auto-instrumented via OpenTelemetry

4. **Metadata to Include**:
   - Agent name (master, worker-coding, worker-analysis)
   - Agent specialty
   - Task ID
   - User ID
   - Model name
   - Token usage

5. **Reference Implementation**:
   See `PHOENIX-INTEGRATION.md` sections:
   - "Phase 2: Python Framework Integration"
   - "Basic Instrumentation" examples
   - "Environment Configuration"

---

## Dashboard Views (Phase 3)

After agents start sending traces, configure these dashboards in Phoenix UI:

### 1. Agent Performance
- Calls/min by agent type
- Latency p50/p95/p99
- Success rate
- Active concurrent agents

### 2. Cost Tracking
- Total tokens consumed
- Cost per agent
- Daily cost trend
- Projected monthly cost

### 3. Error Analysis
- Error rate over time
- Error types distribution
- Failed task chains
- Retry patterns

### 4. Chain Visualization
- Master → worker flows
- Task execution timeline
- Parallel vs sequential patterns
- Bottleneck identification

---

## MCP Server (Phase 4 - Future)

Planned capabilities for programmatic Phoenix queries:

- `query_metrics(agent_name, time_range, metric_type)` → metrics
- `get_traces(agent_name, status, limit)` → traces
- `analyze_errors(time_range, agent_name)` → error_summary
- `get_cost_summary(time_range, agent_name)` → cost_data

See `PHOENIX-INTEGRATION.md` section "Phase 4: Phoenix MCP Server" for implementation details.

---

## Success Criteria

- [x] Phoenix deployment manifest created
- [x] Service configuration with all required ports
- [x] Ingress configuration with TLS
- [x] Database initialization job
- [x] Integration guide documented
- [x] Dashboard views documented
- [x] MCP server design documented
- [x] Manifests committed to Git
- [x] Pushed to GitHub
- [ ] ArgoCD synced (waiting, auto-sync enabled)
- [ ] Phoenix pod running
- [ ] Database initialized
- [ ] UI accessible at observability.ry-ops.dev
- [ ] OTLP endpoint accepting traces

---

## Next Actions

### Immediate (Automatic)
1. ArgoCD will sync within 3 minutes
2. Phoenix pod will start
3. Database init job will run
4. Ingress will be created
5. TLS certificate will be provisioned

### Agent 2 (Python Framework)
1. Install Phoenix Python packages
2. Implement tracer initialization
3. Instrument master agent
4. Instrument worker agents
5. Add metadata to all Claude API calls
6. Test trace collection

### After Integration
1. Verify traces appearing in Phoenix UI
2. Configure 4 dashboard views
3. Set up cost tracking
4. Monitor error rates
5. Plan MCP server implementation

---

## Troubleshooting

### Phoenix Pod Not Starting
```bash
kubectl describe pod -n cortex-knowledge -l app=phoenix
kubectl logs -n cortex-knowledge -l app=phoenix
```

### Database Connection Issues
```bash
# Check PostgreSQL is accessible
kubectl exec -n cortex-knowledge -it <phoenix-pod> -- \
  nc -zv postgres.cortex-system.svc.cluster.local 5432
```

### Ingress Not Accessible
```bash
kubectl get ingress -n cortex-knowledge phoenix -o yaml
kubectl describe ingress -n cortex-knowledge phoenix
kubectl get certificate -n cortex-knowledge phoenix-tls
```

### OTLP Traces Not Appearing
```bash
# Check Phoenix logs
kubectl logs -n cortex-knowledge -l app=phoenix | grep -i otlp

# Test from agent pod
kubectl exec -it <agent-pod> -- \
  telnet phoenix.cortex-knowledge.svc.cluster.local 4317
```

---

## References

- **Deployment**: `/Users/ryandahlberg/Projects/cortex-gitops/apps/cortex-knowledge/`
- **Integration Guide**: `PHOENIX-INTEGRATION.md`
- **Phoenix Docs**: https://docs.arize.com/phoenix
- **OpenTelemetry**: https://opentelemetry.io/docs/
- **GitOps Repo**: https://github.com/ry-ops/cortex-gitops
- **Platform Repo**: https://github.com/ry-ops/cortex-platform

---

**Status**: Phase 1 Complete - Ready for Agent 2 Integration
**Deployed By**: Claude Code (Control Plane)
**Deployment Method**: GitOps (ArgoCD auto-sync)
