# Shared Services Migration Plan
**Date**: 2026-01-16
**Status**: Planning Phase
**Priority**: HIGH

---

## Problem Statement

Critical AI infrastructure services are currently **locked in cortex-school namespace**:
- MoE Router (Mixture of Experts) - AI model routing
- Qdrant - Vector database for RAG
- RAG Validator - Retrieval validation
- Health Monitor - Service health checks
- Implementation Workers - Task execution
- School Coordinator - Orchestration

**Impact**: Other Cortex services cannot use these capabilities. YouTube ingestion, cortex-chat, MCP servers, etc. are blocked from using MoE routing and RAG.

---

## Solution: Copy to Shared Namespace

**Strategy**: Build, Extend, Retool (Peter and Paul)
1. **Copy** services to shared namespace (new infrastructure)
2. **Migrate** consumers gradually to shared services
3. **Decom** cortex-school duplicates when school development resumes

---

## Target Namespace: cortex-ai-infra

**Why cortex-ai-infra**:
- Already exists (created 2026-01-07)
- Purpose-built for AI infrastructure
- Labeled: `app.kubernetes.io/part-of: cortex`
- Currently has network fabric monitor (5 pods running)

**Alternative**: Could use `cortex-system`, but cortex-ai-infra is more semantically correct.

---

## Services to Migrate

### 1. MoE Router (CRITICAL)
**Current**: cortex-school/moe-router
**Purpose**: Routes requests to appropriate AI models (Haiku, Sonnet, Opus, local)
**Why Shared**: Every service needs intelligent model selection
**Consumers**:
- cortex-chat (chat routing)
- youtube-ingestion (video analysis)
- cortex-system (MCP servers)
- cortex-dev (code generation)
- Future: cortex-llm (local model routing)

**Migration**:
- Copy deployment to cortex-ai-infra/moe-router
- Expose via ClusterIP service accessible cluster-wide
- Update consumers to point to new service
- Keep cortex-school copy until decom

---

### 2. Qdrant (CRITICAL)
**Current**: cortex-school/qdrant (StatefulSet)
**Purpose**: Vector database for embeddings and RAG
**Why Shared**: Knowledge store for entire Cortex
**Consumers**:
- youtube-ingestion (store video embeddings)
- cortex-chat (semantic search)
- cortex-knowledge (knowledge graph integration)
- MoE router (context-aware routing)

**Migration**:
- Copy StatefulSet to cortex-ai-infra/qdrant
- Copy PVC (persistent volume claim) OR start fresh
- Expose via ClusterIP service
- Migrate data OR rebuild embeddings (TBD)
- Keep cortex-school copy until decom

**Data Strategy**:
- Option A: Fresh start (rebuild embeddings from sources)
- Option B: Copy PVC data (complex, risky)
- **Recommendation**: Fresh start - cleaner, safer

---

### 3. RAG Validator
**Current**: cortex-school/rag-validator
**Purpose**: Validates retrieval-augmented generation results
**Why Shared**: Quality control for all AI responses
**Consumers**:
- cortex-chat (validate responses)
- youtube-ingestion (validate analysis)
- Any service using RAG pattern

**Migration**:
- Copy deployment to cortex-ai-infra/rag-validator
- Expose via ClusterIP service
- Update consumers

---

### 4. Health Monitor
**Current**: cortex-school/health-monitor
**Purpose**: Monitors service health across cluster
**Why Shared**: Should monitor ALL Cortex services, not just school
**Consumers**:
- Monitoring/alerting systems
- Auto-healing mechanisms
- Dashboard displays

**Migration**:
- Copy deployment to cortex-ai-infra/health-monitor
- Grant ClusterRole to access all namespaces
- Expose metrics endpoint
- Integrate with Prometheus

---

### 5. Implementation Workers
**Current**: cortex-school/implementation-workers
**Purpose**: Executes tasks from Redis queue, commits to GitHub
**Why Shared**: General task execution, not school-specific
**Consumers**:
- Any service that queues implementation tasks
- Auto-fix daemon
- CI/CD pipelines

**Migration**:
- Copy deployment to cortex-ai-infra/implementation-workers
- Share Redis queue (already in cortex namespace)
- Update RBAC for cluster-wide access
- Keep school-specific workers in cortex-school later

---

### 6. School Coordinator
**Current**: cortex-school/school-coordinator
**Purpose**: Orchestrates learning pipeline
**Why Maybe NOT Shared**: This might actually be school-specific
**Decision**: SKIP for now - evaluate during school development

**Recommendation**: Leave in cortex-school, don't migrate.

---

## Migration Phases

### Phase 1: Setup cortex-ai-infra Infrastructure (IMMEDIATE)
**Goal**: Prepare namespace and shared resources

**Tasks**:
- [ ] Create ResourceQuota for cortex-ai-infra
- [ ] Create LimitRange for cortex-ai-infra
- [ ] Create shared ServiceAccounts and RBAC
- [ ] Document service endpoints

**Resources Needed**:
```yaml
quota:
  limits.cpu: "16"
  limits.memory: "32Gi"
  requests.cpu: "4"
  requests.memory: "8Gi"
  persistentvolumeclaims: "5"
  pods: "30"
```

**Duration**: Immediate (manifests only)

---

### Phase 2: Deploy MoE Router (HIGHEST PRIORITY)
**Goal**: Enable model routing for all services

**Tasks**:
- [ ] Copy moe-router deployment manifest
- [ ] Update namespace to cortex-ai-infra
- [ ] Create Service with stable DNS name
- [ ] Verify routing works
- [ ] Document API endpoints

**Service DNS**: `moe-router.cortex-ai-infra.svc.cluster.local:8080`

**Testing**: Send test request from cortex namespace

**Duration**: 1 deployment cycle (~3 minutes via ArgoCD)

---

### Phase 3: Deploy Qdrant (HIGH PRIORITY)
**Goal**: Shared vector database for all services

**Tasks**:
- [ ] Copy qdrant StatefulSet manifest
- [ ] Update namespace to cortex-ai-infra
- [ ] Create new PVC (50Gi) - fresh start
- [ ] Create Service with stable DNS name
- [ ] Rebuild embeddings from sources (if needed)
- [ ] Verify vector search works

**Service DNS**: `qdrant.cortex-ai-infra.svc.cluster.local:6333`

**Data Strategy**: Fresh start (don't copy data from cortex-school)

**Duration**: 1 deployment cycle + data rebuild time

---

### Phase 4: Deploy RAG Validator (MEDIUM PRIORITY)
**Goal**: Quality validation for all RAG responses

**Tasks**:
- [ ] Copy rag-validator deployment manifest
- [ ] Update namespace to cortex-ai-infra
- [ ] Connect to shared Qdrant
- [ ] Create Service
- [ ] Verify validation works

**Service DNS**: `rag-validator.cortex-ai-infra.svc.cluster.local:8080`

**Duration**: 1 deployment cycle

---

### Phase 5: Deploy Health Monitor (MEDIUM PRIORITY)
**Goal**: Cluster-wide health monitoring

**Tasks**:
- [ ] Copy health-monitor deployment manifest
- [ ] Update namespace to cortex-ai-infra
- [ ] Grant ClusterRole for all namespaces
- [ ] Create Service
- [ ] Expose metrics to Prometheus
- [ ] Create Grafana dashboard

**Service DNS**: `health-monitor.cortex-ai-infra.svc.cluster.local:8080`

**RBAC**: Needs cluster-wide read access

**Duration**: 1 deployment cycle

---

### Phase 6: Deploy Implementation Workers (LOW PRIORITY)
**Goal**: General task execution capability

**Tasks**:
- [ ] Copy implementation-workers deployment manifest
- [ ] Update namespace to cortex-ai-infra
- [ ] Connect to shared Redis queue (cortex namespace)
- [ ] Update RBAC for cluster-wide access
- [ ] Create Service
- [ ] Verify task execution works

**Service DNS**: `implementation-workers.cortex-ai-infra.svc.cluster.local:8080`

**Duration**: 1 deployment cycle

---

## Consumer Migration Strategy

**After each service is deployed to cortex-ai-infra:**

1. **Update Service Discovery**:
   - Change DNS from `<service>.cortex-school.svc.cluster.local`
   - To: `<service>.cortex-ai-infra.svc.cluster.local`

2. **Update Environment Variables**:
   - Example: `MOE_ROUTER_URL=http://moe-router.cortex-ai-infra.svc.cluster.local:8080`

3. **Gradual Rollout**:
   - Update 1 consumer at a time
   - Verify functionality
   - Move to next consumer

4. **Monitor**:
   - Check logs for errors
   - Verify requests reaching new services
   - Confirm responses correct

---

## Decommissioning cortex-school Copies (FUTURE)

**When**: After school development resumes and we verify no dependencies

**Process**:
1. Verify all consumers using cortex-ai-infra services
2. Check cortex-school service logs (should be zero requests)
3. Scale cortex-school copies to 0 replicas
4. Monitor for 48 hours
5. Delete manifests from cortex-school
6. Clean up PVCs

**Timeline**: TBD when school work resumes

---

## Service Endpoints Reference

After migration, these will be the canonical endpoints:

| Service | Endpoint | Port | Protocol |
|---------|----------|------|----------|
| MoE Router | moe-router.cortex-ai-infra.svc.cluster.local | 8080 | HTTP |
| Qdrant | qdrant.cortex-ai-infra.svc.cluster.local | 6333 | HTTP |
| RAG Validator | rag-validator.cortex-ai-infra.svc.cluster.local | 8080 | HTTP |
| Health Monitor | health-monitor.cortex-ai-infra.svc.cluster.local | 8080 | HTTP |
| Implementation Workers | implementation-workers.cortex-ai-infra.svc.cluster.local | 8080 | HTTP |

---

## Resource Requirements

**Total for all shared services (cortex-ai-infra)**:

```yaml
Combined Requests:
  cpu: ~500m
  memory: ~2Gi

Combined Limits:
  cpu: ~4000m
  memory: ~8Gi

Storage:
  qdrant-data: 50Gi PVC
```

**Cluster Impact**: Should be acceptable after freeing up cortex-school resources

---

## Rollback Strategy

**If migration fails**:
1. Services in cortex-school still running (unchanged)
2. Update consumers back to cortex-school endpoints
3. Delete failed cortex-ai-infra deployments
4. No data loss (fresh start strategy)

**Risk Level**: LOW (copy, don't move)

---

## Current State Files to Copy

Need to read these manifests from cortex-school:
- `apps/cortex-school/moe-router-deployment.yaml`
- `apps/cortex-school/qdrant-statefulset.yaml`
- `apps/cortex-school/rag-validator-deployment.yaml`
- `apps/cortex-school/health-monitor-deployment.yaml`
- `apps/cortex-school/implementation-workers-deployment.yaml`
- `apps/cortex-school/school-coordinator-deployment.yaml` (skip)

---

## Next Steps

1. **Immediate**: Read existing manifests from cortex-school
2. **Create**: New manifests in cortex-ai-infra with updated namespaces
3. **Deploy**: Via Git commit → ArgoCD sync
4. **Verify**: Services running and accessible
5. **Migrate**: Update consumers one at a time
6. **Monitor**: Ensure stability
7. **Document**: Update service catalog

---

## Success Criteria

✅ All shared services running in cortex-ai-infra
✅ Services accessible from any namespace
✅ Zero service disruption during migration
✅ cortex-school services still operational (until decom)
✅ Consumers updated and using new endpoints
✅ Resource usage acceptable
✅ Monitoring shows healthy state

---

## Open Questions

1. **Qdrant Data**: Fresh start or copy? **Recommendation: Fresh start**
2. **School Coordinator**: Migrate or leave? **Recommendation: Leave in school**
3. **Redis Queue**: Already shared in cortex namespace - keep there?
4. **ArgoCD Application**: Create cortex-ai-infra-services app?
5. **Monitoring**: Integrate with existing Prometheus/Grafana?

---

*"These services were born in school, but they're needed by the entire Cortex."*

Ready to execute when you give the word.
