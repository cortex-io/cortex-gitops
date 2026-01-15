# Cortex System Status Report

**Generated**: 2026-01-15 11:52 PST
**Cluster**: k3s-production (7 nodes)
**GitOps**: ArgoCD v2.13+

---

## Executive Summary

### Cluster Health
- **Total Resources**: 1,114 Kubernetes objects across 56 namespaces
- **Nodes**: 7 total (3 masters, 4 workers) - All healthy
- **ArgoCD Applications**: 11 managed applications
- **Sync Status**: 3 Synced, 8 OutOfSync (requires investigation)
- **Health Status**: 2 Healthy, 2 Progressing, 7 Degraded

### Critical Issues
1. **Memory Pressure**: 5 Cortex School pods pending due to insufficient memory
2. **ArgoCD Drift**: 8 applications showing OutOfSync status
3. **Service Degradation**: Multiple applications in Degraded health state

---

## ArgoCD Applications Status

| Application | Namespace | Sync Status | Health Status | Resources |
|-------------|-----------|-------------|---------------|-----------|
| checkmk | checkmk | ✅ Synced | 🟡 Progressing | 5 |
| cortex-chat | cortex-chat | ⚠️ OutOfSync | 🔴 Degraded | 64 |
| cortex-cicd | cortex-cicd | ⚠️ OutOfSync | 🟡 Progressing | 12 |
| cortex-core | cortex | ⚠️ OutOfSync | 🔴 Degraded | 82 |
| cortex-csaf | cortex-csaf | ⚠️ OutOfSync | ✅ Healthy | 34 |
| cortex-dev | cortex-dev | ⚠️ OutOfSync | 🔴 Degraded | 32 |
| cortex-knowledge | cortex-knowledge | ⚠️ OutOfSync | 🔴 Degraded | 66 |
| cortex-school | cortex-school | ✅ Synced | 🔴 Degraded | 28 |
| cortex-security | cortex-security | ⚠️ OutOfSync | 🔴 Degraded | 31 |
| cortex-system | cortex-system | ⚠️ OutOfSync | 🔴 Degraded | 203 |
| default-apps | default | ✅ Synced | ✅ Healthy | N/A |

**Total GitOps-Managed Resources**: ~557 resources

---

## Node Resource Utilization

| Node | CPU Usage | CPU % | Memory Usage | Memory % | Capacity |
|------|-----------|-------|--------------|----------|----------|
| k3s-master01 | 643m | 10% | 4030Mi | 68% | 6GB RAM, 6 CPU |
| k3s-master02 | 623m | 10% | 3949Mi | 66% | 6GB RAM, 6 CPU |
| k3s-master03 | 584m | 9% | 4089Mi | 69% | 6GB RAM, 6 CPU |
| k3s-worker01 | 528m | 8% | 2422Mi | 40% | 6GB RAM, 6 CPU |
| k3s-worker02 | 339m | 5% | 3188Mi | 53% | 6GB RAM, 6 CPU |
| k3s-worker03 | 995m | 16% | 2954Mi | 49% | 6GB RAM, 6 CPU |
| k3s-worker04 | 764m | 12% | 4279Mi | 72% | 6GB RAM, 6 CPU |

**Analysis**:
- Master nodes running at 66-69% memory utilization (high)
- k3s-worker04 at 72% memory (very high)
- 2 master nodes have `CriticalAddonsOnly` taint preventing workload scheduling
- 5 worker nodes insufficient memory for new cortex-school pods

---

## Cortex School Status (Autonomous Learning Pipeline)

### Overview
**Namespace**: cortex-school
**ArgoCD Status**: ✅ Synced / 🔴 Degraded
**Deployed**: 2026-01-15 03:15 UTC (commit: 3bcf9184)

### Pod Status

| Service | Replicas | Status | Issue |
|---------|----------|--------|-------|
| school-coordinator | 1/1 | ✅ Running | None |
| health-monitor | 1/1 | ✅ Running | None |
| moe-router | 0/1 | 🔴 Pending | Insufficient memory |
| rag-validator | 0/2 | 🔴 Pending | Insufficient memory |
| implementation-workers | 0/3 | 🔴 Pending | Insufficient memory |
| qdrant | 0/1 | 🔴 Pending | Insufficient memory |

**Total**: 2/9 pods running (22% availability)

### Scheduling Failures
```
Warning: 0/7 nodes are available
  - 2 nodes: untolerated taint {CriticalAddonsOnly: true}
  - 5 nodes: Insufficient memory
  - Preemption: No victims found for incoming pods
```

### Resource Requests per Pod
- **Memory Request**: 256Mi per pod
- **Memory Limit**: 1Gi per pod
- **Total Memory Requested**: 7 pods × 256Mi = 1.8Gi
- **Total Memory Limit**: 7 pods × 1Gi = 7Gi

**Root Cause**: Workers and masters are already at 40-72% memory utilization. New pods requesting 256Mi each cannot be scheduled without evicting existing workloads.

### Services & Networking
All 6 services created successfully:
- ✅ school-coordinator (ClusterIP, port 8080)
- ✅ health-monitor (ClusterIP, port 8080)
- ✅ moe-router (ClusterIP, port 8080)
- ✅ rag-validator (ClusterIP, port 8080)
- ✅ implementation-workers (ClusterIP, port 8080)
- ✅ qdrant (ClusterIP, port 6333)

### RBAC & Permissions
All ServiceAccounts, ClusterRoles, and ClusterRoleBindings created successfully:
- ✅ school-coordinator ServiceAccount
- ✅ health-monitor ServiceAccount
- ✅ implementation-worker ServiceAccount
- ✅ ClusterRoles with appropriate permissions
- ✅ ClusterRoleBindings

---

## MCP Servers Status

### Running (9/11 healthy)

| Server | Namespace | Status | Endpoint |
|--------|-----------|--------|----------|
| cortex-mcp-server | cortex-system | ✅ Running | cortex-mcp.ry-ops.dev |
| cortex-desktop-mcp | cortex | ✅ Running | 10.88.145.216:8765 |
| github-security-mcp-server | cortex-system | ✅ Running | Internal |
| checkmk-mcp-server | cortex-system | ✅ Running | Internal |
| github-mcp-server | cortex-system | ✅ Running | Internal |
| youtube-mcp-server | cortex-system | ✅ Running | Internal |
| n8n-mcp-server | cortex-system | ✅ Running | Internal |
| langflow-mcp-server | cortex-system | ✅ Running | Internal |
| netbox-mcp-server | cortex-system | ✅ Running | Internal |

### Failed (2/11)

| Server | Namespace | Status | Error |
|--------|-----------|--------|-------|
| cloudflare-mcp-server | cortex-system | 🔴 CrashLoopBackOff | 881 restarts (103s ago) |
| langflow-chat-mcp-server | cortex-system | 🔴 Error | Container failed |

---

## Critical Services Status

### Orchestration Layer
- ✅ **cortex-orchestrator** (cortex-system): 1/1 Running
- ✅ **coordinator-master** (cortex-system): 1/1 Running
- ✅ **cortex-live-cli** (cortex-system): 5/5 Running (DaemonSet)

### Gateway Layer
- ✅ **cortex-desktop-mcp** (cortex): Running - LoadBalancer 10.88.145.216:8765
- ✅ **cortex-chat-frontend** (cortex-chat): Running - LoadBalancer 10.88.145.210:80
- ✅ **cortex-chat-backend-simple** (cortex-chat): 1/1 Running

### Knowledge Layer
- ✅ **knowledge-graph-api** (cortex-knowledge): 2/2 Running
- ✅ **knowledge-dashboard** (cortex-knowledge): 1/1 Running
- ✅ **improvement-detector** (cortex-knowledge): 1/1 Running
- ✅ **phoenix** (cortex-knowledge): 1/1 Running

### Data Layer
- ✅ **redis-master** (cortex): Running
- ✅ **redis-queue** (cortex): Running
- ✅ **postgres-postgresql** (cortex): Running
- ✅ **neo4j** (cortex): Running
- ✅ **knowledge-mongodb** (cortex-knowledge): 1/1 Running

### Development Tools
- ✅ **code-generator** (cortex-dev): 1/1 Running
- ✅ **issue-parser** (cortex-dev): 1/1 Running
- ✅ **redis** (cortex-dev): 1/1 Running

### CSAF (Cost, Security, Audit, Framework)
- ✅ **csaf-registry** (cortex-csaf): 2/2 Running
- ✅ **csaf-runtime** (cortex-csaf): 2/2 Running
- ✅ **csaf-postgres** (cortex-csaf): 1/1 Running
- ✅ **csaf-redis** (cortex-csaf): 1/1 Running

### Degraded Services
- 🔴 **cortex-resource-manager** (cortex-system): 1/2 pods - 1 CrashLoopBackOff (1043 restarts)
- 🔴 **cortex-metrics-collector** (cortex-metrics): 0/1 - CrashLoopBackOff (374 restarts)
- 🔴 **cortex-metrics-exporter** (cortex-metrics): 0/1 - CrashLoopBackOff (382 restarts)
- 🔴 **cortex-report-generator** (cortex-metrics): 0/1 - CrashLoopBackOff (383 restarts)

---

## Infrastructure Services

### Monitoring Stack
- ✅ **Prometheus** (monitoring): Running - 71 resources
- ✅ **Grafana** (monitoring): Running
- ✅ **Prometheus Exporters** (monitoring-exporters): 35 resources

### Security & Compliance
- ✅ **Falco** (cortex-security): 3 pods running
- ✅ **Falco Sidekick** (cortex-security): 1/1 Running
- ✅ **Falco Sidekick UI** (cortex-security): 1/1 Running

### Storage
- ✅ **Longhorn** (longhorn-system): 60 resources - Distributed block storage

### Networking
- ✅ **Traefik** (kube-system): LoadBalancer at 10.88.145.200
- ✅ **MetalLB** (metallb-system): 10 resources
- ✅ **Linkerd** (linkerd): 25 resources - Service mesh
- ✅ **Cert-Manager** (cert-manager): 12 resources

### GitOps & CI/CD
- ✅ **ArgoCD** (argocd): 7/7 pods running
- ✅ **Tekton Pipelines** (tekton-pipelines): 29 resources
- ✅ **GitHub Webhook Listener** (cortex-cicd): 1/1 Running (330 restarts)

---

## Local Machine Components

### Claude Desktop
- **Status**: ✅ Running (PID 16425)
- **Memory**: ~128MB
- **MCP Connection**: http://10.88.145.216:8765
- **API Key**: Configured (ending in ...oxQ-q0zTEgAA)

### Claude Code CLI
- **Status**: ✅ Running (PIDs 37996, 74596)
- **Memory**: ~456MB
- **Working Directory**: ~/Projects/cortex-gitops
- **Session**: Active in this terminal

### MCP Clients
- **Active Instances**: 8 Node.js processes
- **Protocol**: JSON-RPC 2.0
- **Target**: cortex-desktop-mcp service

---

## GitOps Repositories

### cortex-gitops (Infrastructure)
- **Location**: ~/Projects/cortex-gitops
- **GitHub**: https://github.com/ry-ops/cortex-gitops
- **Status**: ✅ Clean (up to date with origin/main)
- **Latest Commit**: 59e1f43 (Fix Redis hostname)
- **ArgoCD Sync**: 3-minute polling interval
- **Resources**: 557+ manifests under GitOps control

### cortex-platform (Application Code)
- **Location**: ~/Projects/cortex-platform
- **GitHub**: https://github.com/ry-ops/cortex-platform
- **Contains**: 10,661 files
  - services/: MCP servers, API services, workers
  - coordination/: Agent coordination (5,471 files)
  - lib/: Shared libraries
  - docs/: Documentation

### cortex-k3s (Cluster Documentation)
- **Location**: ~/Projects/cortex-k3s
- **GitHub**: https://github.com/ry-ops/cortex-k3s
- **Purpose**: K3s cluster documentation and setup

---

## Network Architecture

### External Access Points

| Service | Type | External IP | Internal Service | Namespace |
|---------|------|-------------|------------------|-----------|
| cortex-desktop-mcp | LoadBalancer | 10.88.145.216:8765 | cortex-desktop-mcp:8765 | cortex |
| cortex-chat-frontend | LoadBalancer | 10.88.145.210:80 | cortex-chat:80 | cortex-chat |
| cortex-resource-manager | LoadBalancer | 10.88.145.204:8080 | cortex-resource-manager:8080 | cortex-system |
| knowledge-dashboard | LoadBalancer | 10.88.145.208:80 | knowledge-dashboard:80 | cortex-knowledge |
| cortex-metrics-api | LoadBalancer | 10.88.145.209:8080 | cortex-metrics-api:8080 | cortex-metrics |
| Traefik | LoadBalancer | 10.88.145.200 | traefik:80,443 | kube-system |

### DNS Records (ry-ops.dev)
- cortex-mcp.ry-ops.dev → cortex-mcp-server
- chat.ry-ops.dev → cortex-chat-frontend
- knowledge.ry-ops.dev → knowledge-dashboard
- argocd.ry-ops.dev → argocd-server

---

## Recommendations

### Immediate Actions Required

1. **Address Memory Pressure** (Priority: CRITICAL)
   - Option A: Reduce replica counts for non-critical services
   - Option B: Lower memory requests for cortex-school pods (256Mi → 128Mi)
   - Option C: Add more worker nodes or increase node memory
   - Option D: Evict completed/failed jobs and build pods

2. **Fix ArgoCD Drift** (Priority: HIGH)
   - Investigate why 8 applications show OutOfSync status
   - Manual changes may have been made to cluster bypassing GitOps
   - Run: `kubectl get applications -n argocd -o yaml` to compare
   - Consider hard refresh or manual sync for each application

3. **Investigate CrashLooping Services** (Priority: HIGH)
   - cortex-resource-manager (1043 restarts)
   - cortex-metrics-collector (374 restarts)
   - cortex-metrics-exporter (382 restarts)
   - cortex-report-generator (383 restarts)
   - cloudflare-mcp-server (881 restarts)
   - Check logs: `kubectl logs -n <namespace> <pod>`

4. **Optimize Resource Requests** (Priority: MEDIUM)
   - Review resource requests across all namespaces
   - Many pods may be over-provisioned
   - Implement VPA (Vertical Pod Autoscaler) for recommendations
   - Consider ResourceQuotas per namespace

### Long-Term Improvements

1. **Cluster Capacity Planning**
   - Current: 7 nodes × 6GB = 42GB total RAM
   - Used: ~27GB (64% utilization)
   - Available: ~15GB for new workloads
   - Consider: Adding 1-2 worker nodes or upgrading to 8GB RAM per node

2. **GitOps Hygiene**
   - Enforce "no manual changes" policy
   - All changes must go through Git → ArgoCD → Cluster
   - Enable webhook-based sync instead of polling
   - Add pre-commit hooks for manifest validation

3. **Monitoring & Alerting**
   - Set up alerts for pod pending > 5 minutes
   - Alert on CrashLoopBackOff > 10 restarts
   - Monitor memory pressure and send warnings at 80%
   - Track ArgoCD sync failures

4. **Cortex School Optimization**
   - Once running, evaluate actual memory usage vs requests
   - Consider using HPA (Horizontal Pod Autoscaler)
   - Implement pod disruption budgets
   - Add resource quotas to prevent namespace resource exhaustion

---

## Quick Reference Commands

### Check Cluster Health
```bash
kubectl top nodes
kubectl get pods -A | grep -vE "(Running|Completed)"
kubectl get applications -n argocd
```

### Check Cortex School
```bash
kubectl get pods -n cortex-school
kubectl logs -n cortex-school school-coordinator-<pod>
kubectl describe pod -n cortex-school <pending-pod>
```

### Force ArgoCD Sync
```bash
kubectl patch application cortex-school -n argocd \
  --type merge -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
```

### Check Memory Usage
```bash
kubectl top pods -n cortex-school --sort-by=memory
kubectl describe nodes | grep -A 5 "Allocated resources"
```

---

**Report Generated By**: Claude Code (Cortex Control Plane)
**Next Report**: Manual generation on request
**Documentation**: See ~/Desktop/CORTEX-EVERYTHING-BAGEL.md, CORTEX-VISUAL-FLOW.md, CORTEX-ROLES-RESPONSIBILITIES.md
