# Cluster Migration Plan — fabric-forge on k3s

**Status**: Planning
**Last updated**: 2026-02-28
**Author**: Ryan Dahlberg
**Goal**: Strip k3s down to networking/storage/monitoring essentials, deploy the fabric stack cleanly, and manage everything through git-steer + ArgoCD instead of ad-hoc kubectl.

---

## Summary

The k3s cluster has accumulated ~90 deployments across ~80 namespaces from the old cortex-io era. Most of those workloads are no longer needed — fabric-forge replaces them with lean MCP apps routed through fabric-gateway. This document defines what stays, what goes, the order of operations, and the rollback plan.

The guiding principle is **git-steer's zero-footprint model**: state lives in git, GitHub Actions execute changes, the cluster converges through ArgoCD. No more cowboy kubectl.

---

## Decision Table

### KEEP

| Component | Namespace | Why |
|-----------|-----------|-----|
| **Traefik** | kube-system | All ingress routing, MetalLB IP `10.88.145.200` |
| **MetalLB** | metallb-system | L2 LB for Traefik |
| **cert-manager** | cert-manager | TLS certs via `selfsigned-issuer` |
| **ArgoCD** | argocd | GitOps engine for all fabric deployments |
| **Longhorn** | longhorn-system | Storage for fabric PVCs (see below) |
| **KEDA core** | keda | Event-driven scaling for fabric apps |
| **Prometheus + Grafana** | monitoring | Observability — explicitly kept |
| **Sandfly** | sandfly | Security monitoring, 7 k3s nodes active |
| **Tailscale** | tailscale | Subnet router for cluster network access |
| **fabric-gateway** | cortex-system | MoE MCP router, 167 tools |
| **fabric-chat** | cortex-system | 12 chat/semantic-search tools |
| **fabric-k8s** | cortex-system | k8s tools (ClusterRole read) |
| **fabric-pipelines** | cortex-system | 5 CronJob automation pipelines |
| **Redis** | cortex-system | Chat session backing store (fabric-chat) |
| **Qdrant** | cortex-system | Semantic search (fabric-chat + fabric-gateway) |
| **Postgres** | cortex-system | Session metadata (fabric-chat) |

### LONGHORN FABRIC PVCs — Do not touch Longhorn until these are migrated or confirmed not needed

| PVC | Size | Class |
|-----|------|-------|
| redis-data-redis-master-0 | 5Gi | longhorn |
| redis-data-redis-replicas-0/1/2 | 8Gi each | longhorn |
| qdrant-storage | 5Gi | longhorn |
| data-postgres-postgresql-0 | 10Gi | longhorn |
| cortex-terminal-home | 5Gi | longhorn |
| cortex-terminal-tailscale | 1Gi | longhorn |
| data-sandfly-postgres-0 | 10Gi | longhorn-single |

### DECOMMISSION

| Component | Namespace | Reason | Risk |
|-----------|-----------|--------|------|
| **KEDA HTTP add-on** | keda | Crash-looping (1776 restarts), not used by fabric | Low — just delete |
| **Internal Docker registry** | (various) | Fabric uses GHCR. Only `cortex-orchestrator` in cortex-system still references `10.43.170.72:5000` | Low after cortex-orchestrator removed |
| **cortex-orchestrator** | cortex-system | Leftover from old cortex, uses internal registry | Low — just a deployment |
| **Rancher** | cattle-fleet-system, cattle-system, etc. | Only fleet-agent installed, no active Rancher-managed fabric workloads. Rancher manages sealed-secrets, traefik, kube-prometheus-stack — those need to be re-adopted by ArgoCD first | **Medium** — see Phase 3 |
| **Linkerd** | linkerd | Installed but unused by fabric or any remaining workloads | Low |
| **Tekton** | tekton-pipelines | Replaced by GitHub Actions | Low |
| **cortex-* namespaces** | ~80 ns | All workloads backed up in cortex-io GitHub org | Medium — verify ArgoCD adoption first |
| **UniFi from k3s** | (old cortex ns) | fabric-unifi MCP app handles UniFi now | Low |
| **n8n, netbox, nginx-proxy-manager, portainer, velero, vpa** | various | Not part of fabric architecture | Low |

### UNDER REVIEW

| Component | Question | Status |
|-----------|----------|--------|
| **cortex-terminal** | Useful for in-cluster debug? Or replace with `kubectl exec`? | Keep for now, review in Phase 3 |
| **sealed-secrets** | Currently Rancher-managed — needs ArgoCD re-adoption before Rancher removal | Depends on Phase 3 |

---

## Architecture After Migration

```
k3s cluster (cortex-system focus)
├── Networking:  Traefik + MetalLB + cert-manager + Tailscale
├── Storage:     Longhorn (fabric PVCs only)
├── Observability: Prometheus + Grafana + KEDA (core)
├── Security:    Sandfly
├── GitOps:      ArgoCD
└── Fabric stack:
    ├── fabric-gateway  (MoE router, all tools)
    ├── fabric-chat     (chat sessions, semantic search)
    ├── fabric-k8s      (k8s introspection tools)
    ├── fabric-pipelines (5 CronJobs: security-triage, gitops-observer, network-audit, proxmox-k8s, ops-chat)
    ├── Redis           (chat backing store)
    ├── Qdrant          (semantic search)
    └── Postgres        (session metadata)
```

---

## Phased Execution Plan

### Phase 0 — Immediate Safe Cleanup (no ArgoCD changes needed)
**Risk**: Very Low
**Rollback**: `kubectl apply -f` the deleted manifests

1. **Delete KEDA HTTP add-on**: `kubectl delete -n keda deploy/keda-add-ons-http-controller svc/keda-add-ons-http-controller`
   _Rationale: crash-looping 1776 restarts, not used by fabric_

2. **Create ArgoCD GPG configmap**: `kubectl create configmap argocd-gpg-keys-cm -n argocd`
   _Rationale: 24k FailedMount events, noisy logs_

3. **Suspend unschedulable workloads**: `kubectl scale deploy/unifi-reasoning-slm --replicas=0`
   _Rationale: 3Gi request, workers at 89-98% memory, can't schedule_

4. **Remove cortex-orchestrator**: `kubectl delete deploy/cortex-orchestrator -n cortex-system`
   _Rationale: uses internal registry 10.43.170.72:5000, not part of fabric_

**Verify after**: `kubectl get pods -n cortex-system`, `kubectl top nodes`

---

### Phase 1 — Build Execution Dispatch Layer
**Risk**: None (additive only)
**Rollback**: N/A

Before removing anything, build the mechanism that fabric pipelines use to *propose and apply* changes:

1. Create `cortex-gitops/.github/workflows/kubectl-apply.yml` — accepts a kubeconfig command, runs it, reports back to git-steer-state
2. Create `cortex-gitops/.github/workflows/helm-upgrade.yml` — accepts chart name + values override, runs helm upgrade, reports back
3. Wire pipeline 2 (gitops-observer) to dispatch a workflow when diagnosis warrants it
4. Test round-trip: pipeline detects issue → proposes fix → workflow executes → result in git-steer-state

_This is the "shift instabilities right out the window" mechanism._

---

### Phase 2 — Decommission cortex-* Namespaces
**Risk**: Medium (verify no fabric deps first)
**Rollback**: `kubectl apply -f` from cortex-io GitHub backup

**Pre-check**: Run `kubectl get all -n <ns> -o yaml` and verify no fabric apps depend on any service in those namespaces.

Order of removal (safest first):
1. n8n-related namespaces
2. netbox
3. nginx-proxy-manager (Traefik handles routing now)
4. portainer
5. velero
6. vpa
7. Remaining cortex-* namespaces (cortex-school, cortex-social, cortex-reasoning, etc.)
8. Internal Docker registry (after all references removed)

**After each**: Check ArgoCD UI, check `kubectl get events --field-selector type=Warning -A | head -50`

---

### Phase 3 — Rancher Removal
**Risk**: Medium-High
**Rollback**: Reinstall Rancher Helm chart (non-trivial)

Rancher currently manages: sealed-secrets, traefik, kube-prometheus-stack. Before removing Rancher:

1. Verify ArgoCD has its own copies of those Helm charts in cortex-gitops
2. If not: add ArgoCD Applications for sealed-secrets and kube-prometheus-stack
3. Run `kubectl get managedchart -A` to see everything Rancher controls
4. Annotate each resource with `argocd.argoproj.io/managed-by: argocd` to re-adopt
5. Remove Rancher: `helm uninstall rancher -n cattle-system`
6. Clean up: `kubectl delete ns cattle-system cattle-fleet-system cattle-global-data cattle-global-nt`

**Timing**: Do this only after Phase 2 is clean and the cluster has been stable for at least a week.

---

### Phase 4 — Linkerd + Tekton Removal
**Risk**: Low
**Rollback**: Reinstall via Helm

1. Verify no fabric service uses Linkerd annotations (`kubectl get pods -A -o yaml | grep linkerd`)
2. `helm uninstall linkerd-control-plane -n linkerd` (or via ArgoCD deletion)
3. `kubectl delete ns linkerd linkerd-viz`
4. `kubectl delete ns tekton-pipelines`

---

### Phase 5 — Wire Pipelines to Close the MTTR Loop
**Risk**: Low (additive)

1. Pipeline 2 (gitops-observer) → on diagnosis, dispatch `kubectl-apply.yml` with fix command
2. Pipeline 1 (security-triage) → on critical CVE, dispatch `helm-upgrade.yml` for affected service
3. All pipelines → write MTTR metrics to git-steer-state `metrics/` path
4. Build a simple dashboard query: MTTR per pipeline per month from git-steer-state JSONL

---

## Data at Risk

| Data | Location | Backup | Risk |
|------|----------|--------|------|
| Chat sessions + embeddings | git-steer-state + Qdrant PVC | Git (sessions), no backup for vectors | Medium — vector DB not backed up |
| Redis session cache | Redis PVC | No persistent backup | Low — cache only, rebuilt on use |
| Postgres session metadata | Postgres PVC | No backup | Medium — lose session history |
| Sandfly scan data | sandfly-postgres PVC | No backup | Low — Sandfly rescans automatically |

**Recommendation**: Before any PVC-touching operations, snapshot via Longhorn UI or `kubectl exec` pg_dump.

---

## Rollback Strategy

- **Phases 0-1**: Fully reversible (`kubectl apply` from backup)
- **Phase 2**: Reversible from cortex-io GitHub org (re-apply Helm charts)
- **Phase 3 (Rancher)**: Hard to reverse. Do not proceed without ArgoCD re-adoption of all Rancher-managed resources
- **Phase 4**: Easy (Helm reinstall)
- **Phase 5**: Additive, no rollback needed

---

## Change Log

| Date | Phase | Action | Author |
|------|-------|--------|--------|
| 2026-02-28 | Planning | Document created, decisions finalized | Ryan |

---

## Open Items

- [ ] Phase 0: Apply KEDA HTTP add-on deletion
- [ ] Phase 0: Create argocd-gpg-keys-cm
- [ ] Phase 0: Suspend unifi-reasoning-slm
- [ ] Phase 0: Remove cortex-orchestrator from cortex-system
- [ ] Phase 1: Design + implement dispatch workflows in cortex-gitops
- [ ] Longhorn: Evaluate Longhorn backup strategy before Phase 2 begins
- [ ] Rancher: Run `kubectl get managedchart -A` to get full list of Rancher-managed resources
- [ ] cortex-terminal: Decide keep/remove before Phase 2
