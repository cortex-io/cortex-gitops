# Cortex Visual Flow Diagram

**Complete Data Flow Architecture**
**Date**: 2026-01-15

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACES                                 │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐ │
│  │ Claude Desktop  │  │   Claude Code   │  │  Web Chat Interface     │ │
│  │     (Local)     │  │     (CLI)       │  │  (chat.ry-ops.dev)      │ │
│  └────────┬────────┘  └────────┬────────┘  └───────────┬─────────────┘ │
│           │                    │                        │                │
└───────────┼────────────────────┼────────────────────────┼────────────────┘
            │                    │                        │
            └───────────┬────────┴───────────┬────────────┘
                        │                    │
                        ↓                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│                         GATEWAY LAYER                                     │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌────────────────────────────────┐   ┌───────────────────────────────┐ │
│  │    cortex-desktop-mcp          │   │   cortex-chat-frontend        │ │
│  │    (10.88.145.216:8765)        │   │   (10.88.145.210:80)          │ │
│  │    ─ MCP Protocol Gateway      │   │   ─ Web UI                    │ │
│  │    ─ Bridges local to cluster  │   │   ─ API proxy                 │ │
│  └────────────────┬───────────────┘   └────────────┬──────────────────┘ │
│                   │                                 │                    │
│                   └────────────┬────────────────────┘                    │
│                                │                                         │
└────────────────────────────────┼─────────────────────────────────────────┘
                                 │
                                 ↓
┌──────────────────────────────────────────────────────────────────────────┐
│                         MCP ROUTING LAYER                                 │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                     cortex-mcp-server                              │ │
│  │                   (cortex-mcp.ry-ops.dev)                          │ │
│  │                                                                    │ │
│  │   ┌──────────────┐  ┌─────────────┐  ┌────────────────────────┐ │ │
│  │   │ Tool Router  │  │  Context    │  │  Authentication       │ │ │
│  │   │              │  │  Manager    │  │                        │ │ │
│  │   └──────┬───────┘  └──────┬──────┘  └───────────┬──────────┘ │ │
│  │          │                  │                     │            │ │
│  └──────────┼──────────────────┼─────────────────────┼────────────┘ │
│             │                  │                     │              │
└─────────────┼──────────────────┼─────────────────────┼──────────────┘
              │                  │                     │
              ↓                  ↓                     ↓
┌──────────────────────────────────────────────────────────────────────────┐
│                       SPECIALIZED MCP SERVERS                             │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  │
│  │  sandfly-   │  │  proxmox-   │  │  unifi-     │  │ kubernetes-  │  │
│  │  mcp-server │  │  mcp-server │  │  mcp-server │  │ mcp-server   │  │
│  │ (Security)  │  │ (Infra)     │  │ (Network)   │  │ (K8s Ops)    │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬───────┘  │
│         │                │                │                │           │
│  ┌──────────────┐  ┌─────────────┐  ┌───────────────┐  ┌──────────┐  │
│  │  checkmk-    │  │  github-    │  │  n8n-         │  │ (more)   │  │
│  │  mcp-server  │  │  security-  │  │  mcp-server   │  │          │  │
│  │ (Monitoring) │  │  mcp-server │  │ (Automation)  │  │          │  │
│  └──────┬───────┘  └──────┬──────┘  └──────┬────────┘  └──────┬───┘  │
│         │                 │                 │                  │       │
└─────────┼─────────────────┼─────────────────┼──────────────────┼───────┘
          │                 │                 │                  │
          └─────────────────┴─────────────────┴──────────────────┘
                                    │
                                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATION LAYER                                │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │               cortex-orchestrator (cortex-system)                   ││
│  │              ─ Main API orchestration                               ││
│  │              ─ Task routing & coordination                          ││
│  │              ─ Multi-agent workflow management                      ││
│  └──────────────────────────┬──────────────────────────────────────────┘│
│                              │                                           │
│                              ↓                                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                   redis-master (Task Queue)                       │  │
│  │                  cortex:queue:{critical|high|medium|low}          │  │
│  └──────────────────────────┬───────────────────────────────────────┘  │
│                              │                                           │
└──────────────────────────────┼───────────────────────────────────────────┘
                               │
                               ↓
┌──────────────────────────────────────────────────────────────────────────┐
│                           WORKER LAYER                                    │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                cortex-queue-worker (2-25 replicas)                 │ │
│  │                     ─ Process queued tasks                         │ │
│  │                     ─ HPA scaling based on load                    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  Calls specialized services based on task type:                          │
│                                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  ┌────────────┐│
│  │ code-        │  │ issue-       │  │ documentation-│  │ cost-      ││
│  │ generator    │  │ parser       │  │ master        │  │ tracker    ││
│  └──────────────┘  └──────────────┘  └───────────────┘  └────────────┘│
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────────────┐
│                    AUTONOMOUS LEARNING PIPELINE                           │
│                        (Cortex Online School)                             │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  YouTube Videos                                                           │
│       ↓                                                                   │
│  ┌──────────────────────┐                                                │
│  │ youtube-ingestion    │ ← CronJob: Hourly                              │
│  │ ─ Fetch transcripts  │                                                │
│  │ ─ Claude analysis    │                                                │
│  │ ─ Generate 25        │                                                │
│  │   improvement ideas  │                                                │
│  └──────┬───────────────┘                                                │
│         │                                                                 │
│         ↓                                                                 │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │         redis-queue: improvements:raw                            │   │
│  │         (Sorted set with relevance scores)                       │   │
│  └──────┬───────────────────────────────────────────────────────────┘   │
│         │                                                                 │
│         ↓                                                                 │
│  ┌──────────────────────┐                                                │
│  │ school-coordinator   │ ✅ RUNNING                                     │
│  │ ─ Monitors queue     │                                                │
│  │ ─ Orchestrates flow  │                                                │
│  │ ─ Auto-approval      │                                                │
│  └──────┬───────────────┘                                                │
│         │                                                                 │
│         ↓                                                                 │
│  ┌──────────────────────┐                                                │
│  │    moe-router        │ ⏳ PENDING (memory)                            │
│  │                      │                                                │
│  │ Routes to 6 experts: │                                                │
│  │ ┌─────────────────┐  │                                                │
│  │ │ Architecture    │  │ Claude Opus 4.5   (system design)             │
│  │ │ Integration     │  │ Claude Sonnet 4.5 (tool integration)          │
│  │ │ Security        │  │ Claude Opus 4.5   (auth, compliance)          │
│  │ │ Database        │  │ Claude Sonnet 4.5 (schema, migrations)        │
│  │ │ Networking      │  │ Claude Sonnet 4.5 (ingress, mesh)             │
│  │ │ Monitoring      │  │ Claude Haiku 4    (metrics, alerts)           │
│  │ └─────────────────┘  │                                                │
│  └──────┬───────────────┘                                                │
│         │                                                                 │
│         ↓                                                                 │
│  improvements:categorized (with expert evaluation)                        │
│         │                                                                 │
│         ↓                                                                 │
│  ┌──────────────────────┐                                                │
│  │   rag-validator      │ ⏳ PENDING (memory)                            │
│  │                      │                                                │
│  │ Searches:            │                                                │
│  │ ├─ cortex-docs       │ (architecture conflicts)                       │
│  │ ├─ cortex-gitops     │ (duplicate implementations)                    │
│  │ └─ qdrant            │ (past improvements via vector search)          │
│  │                      │                                                │
│  │ Connected to:        │                                                │
│  │  qdrant-0            │ ⏳ PENDING (StatefulSet, 20Gi storage)         │
│  │  (Vector DB)         │                                                │
│  └──────┬───────────────┘                                                │
│         │                                                                 │
│         ↓                                                                 │
│  improvements:validated                                                   │
│         │                                                                 │
│         ↓                                                                 │
│  ┌──────────────────────┐                                                │
│  │ Auto-Approval Gate   │                                                │
│  │                      │                                                │
│  │ IF relevance ≥ 90%   │────────────┐                                   │
│  │ AND no conflicts     │            │                                   │
│  │ AND safe category    │            │                                   │
│  └──────┬───────────────┘            │                                   │
│         │ YES                        │ NO                                │
│         ↓                            ↓                                   │
│  improvements:approved     improvements:pending_review                    │
│         │                                                                 │
│         ↓                                                                 │
│  ┌──────────────────────────────────┐                                    │
│  │  implementation-workers (3)      │ ⏳ PENDING (memory)                │
│  │                                  │                                    │
│  │  Specialized by type:            │                                    │
│  │  ├─ Architecture  (manifests)    │                                    │
│  │  ├─ Integration   (services)     │                                    │
│  │  ├─ Security      (RBAC)         │                                    │
│  │  ├─ Database      (migrations)   │                                    │
│  │  └─ Monitoring    (dashboards)   │                                    │
│  │                                  │                                    │
│  │  Actions:                        │                                    │
│  │  1. Generate K8s manifests       │                                    │
│  │  2. Create Git commit            │                                    │
│  │  3. Push to cortex-gitops        │                                    │
│  └──────┬───────────────────────────┘                                    │
│         │                                                                 │
│         ↓                                                                 │
│  ┌──────────────────────────────────┐                                    │
│  │ GitHub: cortex-gitops            │                                    │
│  │ ─ New commit with manifests      │                                    │
│  │ ─ Detailed commit message        │                                    │
│  │ ─ Co-authored by Cortex School   │                                    │
│  └──────┬───────────────────────────┘                                    │
│         │                                                                 │
│         ↓                                                                 │
│  ┌──────────────────────────────────┐                                    │
│  │        ArgoCD                    │                                    │
│  │ ─ Polls GitHub every 3 min       │                                    │
│  │ ─ Detects new commit             │                                    │
│  │ ─ Auto-syncs to cluster          │                                    │
│  │ ─ Self-heals drift               │                                    │
│  └──────┬───────────────────────────┘                                    │
│         │                                                                 │
│         ↓                                                                 │
│  ┌──────────────────────────────────┐                                    │
│  │  Kubernetes Deployment           │                                    │
│  │  ─ New pods/services created     │                                    │
│  │  ─ Resources updated             │                                    │
│  └──────┬───────────────────────────┘                                    │
│         │                                                                 │
│         ↓                                                                 │
│  improvements:deployed                                                    │
│         │                                                                 │
│         ↓                                                                 │
│  ┌──────────────────────────────────┐                                    │
│  │    health-monitor                │ ✅ RUNNING                         │
│  │                                  │                                    │
│  │ Monitors for 5 minutes:          │                                    │
│  │ ├─ Pod status (Running/Ready)    │                                    │
│  │ ├─ Readiness probes              │                                    │
│  │ ├─ Prometheus metrics            │                                    │
│  │ │  (error rate, latency)         │                                    │
│  │ ├─ Logs (ERROR/FATAL/panic)      │                                    │
│  │ └─ Dependency connectivity       │                                    │
│  │                                  │                                    │
│  │ IF ALL PASS:                     │                                    │
│  │   → improvements:verified ✅      │                                    │
│  │                                  │                                    │
│  │ IF ANY FAIL:                     │                                    │
│  │   1. git revert <commit>         │                                    │
│  │   2. Push rollback               │                                    │
│  │   3. Force ArgoCD sync           │                                    │
│  │   4. Verify healthy              │                                    │
│  │   5. Log failure                 │                                    │
│  │   → improvements:failed ❌        │                                    │
│  └──────────────────────────────────┘                                    │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────────────┐
│                     KNOWLEDGE & INTELLIGENCE LAYER                        │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    Documentation Ingestion                         │ │
│  │                                                                    │ │
│  │  CronJob (daily 2am)                                               │ │
│  │       ↓                                                            │ │
│  │  documentation-master                                              │ │
│  │       ↓                                                            │ │
│  │  [Crawls: GitHub repos, docs sites, wikis]                        │ │
│  │       ↓                                                            │ │
│  │  docling-service (structure-aware processing)                     │ │
│  │       ↓                                                            │ │
│  │  knowledge-extractor                                               │ │
│  │       ↓                                                            │ │
│  │  ┌────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │ │
│  │  │ Neo4j Graph    │  │ MongoDB          │  │ Elasticsearch   │  │ │
│  │  │ (relationships)│  │ (documents)      │  │ (full-text)     │  │ │
│  │  └────────┬───────┘  └────────┬─────────┘  └────────┬────────┘  │ │
│  │           └──────────────┬─────────────────────────┘             │ │
│  │                          ↓                                        │ │
│  │              knowledge-graph-api                                  │ │
│  │                          ↓                                        │ │
│  │              knowledge-dashboard                                  │ │
│  │              (10.88.145.208)                                      │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    Improvement Detection                           │ │
│  │                                                                    │ │
│  │  improvement-detector                                              │ │
│  │       ↓                                                            │ │
│  │  [Analyzes: code patterns, metrics, incidents]                    │ │
│  │       ↓                                                            │ │
│  │  [Suggests: optimizations, best practices]                        │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    Observability (Phoenix)                         │ │
│  │                                                                    │ │
│  │  All AI services → OpenTelemetry → phoenix                         │ │
│  │                                                                    │ │
│  │  Dashboard: observability.ry-ops.dev                               │ │
│  │  ─ LLM traces                                                      │ │
│  │  ─ Token usage                                                     │ │
│  │  ─ Latency metrics                                                 │ │
│  │  ─ Cost tracking                                                   │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────────────┐
│                      SECURITY & MONITORING LAYER                          │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Runtime Security (Falco)                                          │ │
│  │                                                                    │ │
│  │  All K8s nodes → Falco DaemonSet                                   │ │
│  │       ↓                                                            │ │
│  │  [Detects: syscalls, file access, network anomalies]              │ │
│  │       ↓                                                            │ │
│  │  falco-falcosidekick (alert forwarding)                           │ │
│  │       ↓                                                            │ │
│  │  falco-falcosidekick-ui (dashboard)                               │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Vulnerability Scanning (Trivy)                                    │ │
│  │                                                                    │ │
│  │  CronJob (daily 2am)                                               │ │
│  │       ↓                                                            │ │
│  │  trivy-cluster-scan                                                │ │
│  │       ↓                                                            │ │
│  │  [Scans: containers, configs, secrets]                            │ │
│  │       ↓                                                            │ │
│  │  [Reports: CVEs, misconfigurations]                               │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  EDR (Sandfly)                                                     │ │
│  │                                                                    │ │
│  │  sandfly-mcp-server → Sandfly API (10.88.140.176)                  │ │
│  │       ↓                                                            │ │
│  │  [Monitors: hosts, processes, network]                            │ │
│  │       ↓                                                            │ │
│  │  sandfly-web (sandfly.ry-ops.dev)                                 │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Security Advisories (CSAF)                                        │ │
│  │                                                                    │ │
│  │  csaf-runtime (processes advisories)                               │ │
│  │       ↓                                                            │ │
│  │  csaf-registry (stores advisories)                                │ │
│  │       ↓                                                            │ │
│  │  csaf-correlator (matches to assets)                              │ │
│  │       ↓                                                            │ │
│  │  csaf-prompt-engine (AI analysis)                                 │ │
│  │       ↓                                                            │ │
│  │  csaf-postgres (persistence)                                       │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────────────┐
│                         DATA PERSISTENCE LAYER                            │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Primary Database (PostgreSQL)                                     │ │
│  │                                                                    │ │
│  │  postgres-postgresql (StatefulSet 1/1)                             │ │
│  │  ─ ClusterIP: 10.43.135.206:5432                                   │ │
│  │  ─ Longhorn persistent volume                                      │ │
│  │  ─ Daily backups (CronJob 2am)                                     │ │
│  │  ─ PostgreSQL exporter (metrics)                                   │ │
│  │  ─ pgAdmin (admin UI)                                              │ │
│  │                                                                    │ │
│  │  Used by:                                                          │ │
│  │  ├─ cortex-orchestrator                                            │ │
│  │  ├─ csaf-postgres                                                  │ │
│  │  ├─ Most application services                                      │ │
│  │  └─ Knowledge graph metadata                                       │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Cache & Queues (Redis)                                            │ │
│  │                                                                    │ │
│  │  redis-master (StatefulSet 1/1)                                    │ │
│  │  ─ ClusterIP: 10.43.48.239:6379                                    │ │
│  │  ─ Persistent volume                                               │ │
│  │                                                                    │ │
│  │  redis-queue (cortex namespace)                                    │ │
│  │  ─ ClusterIP: 10.43.10.63:6379                                     │ │
│  │  ─ Task queues                                                     │ │
│  │  ─ YouTube improvement pipeline                                    │ │
│  │                                                                    │ │
│  │  Multiple Redis instances per namespace:                           │ │
│  │  ├─ cortex-chat/redis (sessions)                                   │ │
│  │  ├─ cortex-dev/redis (dev cache)                                   │ │
│  │  └─ cortex-csaf/redis (advisory cache)                             │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Storage Classes                                                   │ │
│  │                                                                    │ │
│  │  Longhorn (distributed block storage)                              │ │
│  │  ─ Replicated across nodes                                         │ │
│  │  ─ Automatic backups                                               │ │
│  │  ─ Used for: databases, vector stores, logs                        │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────────────┐
│                             GITOPS LAYER                                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                   Source of Truth (GitHub)                         │ │
│  │                                                                    │ │
│  │  ┌──────────────────────────────────────────────────────────────┐ │ │
│  │  │ cortex-gitops                                                │ │ │
│  │  │ ─ 120+ Kubernetes manifests                                  │ │ │
│  │  │ ─ 7 ArgoCD Applications                                      │ │ │
│  │  │ ─ 23 namespaces                                              │ │ │
│  │  └──────────────────────────────────────────────────────────────┘ │ │
│  │                              ↓                                     │ │
│  │  ┌──────────────────────────────────────────────────────────────┐ │ │
│  │  │ cortex-platform                                              │ │ │
│  │  │ ─ Application source code                                    │ │ │
│  │  │ ─ Service implementations                                    │ │ │
│  │  │ ─ 10,661 files                                               │ │ │
│  │  └──────────────────────────────────────────────────────────────┘ │ │
│  │                              ↓                                     │ │
│  │  ┌──────────────────────────────────────────────────────────────┐ │ │
│  │  │ cortex-docs                                                  │ │ │
│  │  │ ─ Architecture documentation                                 │ │ │
│  │  │ ─ Design decisions                                           │ │ │
│  │  │ ─ API specs                                                  │ │ │
│  │  └──────────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    Continuous Deployment (ArgoCD)                  │ │
│  │                                                                    │ │
│  │  Polls GitHub every 3 minutes                                      │ │
│  │       ↓                                                            │ │
│  │  Detects changes in cortex-gitops                                 │ │
│  │       ↓                                                            │ │
│  │  Auto-syncs to cluster                                            │ │
│  │  ─ Self-heal: true (reverts manual changes)                       │ │
│  │  ─ Prune: true (deletes removed resources)                        │ │
│  │  ─ Auto-sync: true                                                │ │
│  │       ↓                                                            │ │
│  │  kubectl apply -f <manifests>                                     │ │
│  │       ↓                                                            │ │
│  │  Kubernetes reconciles state                                      │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## Request Flow Examples

### Example 1: User asks Claude to analyze cluster health

```
User: "Show me unhealthy pods in the cluster"
  ↓
Claude Desktop (local)
  ↓ (MCP JSON-RPC)
cortex-desktop-mcp (10.88.145.216:8765)
  ↓
cortex-mcp-server (mcp routing)
  ↓
kubernetes-mcp-server (specialized tool)
  ↓
K8s API (kubectl get pods --field-selector=status.phase!=Running)
  ↓
Returns: List of unhealthy pods
  ↓
cortex-desktop-mcp
  ↓
Claude Desktop
  ↓
User sees formatted response
```

### Example 2: User requests code generation

```
User: "Generate a Deployment manifest for nginx"
  ↓
Claude Desktop / Code
  ↓
cortex-desktop-mcp
  ↓
cortex-orchestrator
  ↓
redis-master (queue task)
  ↓
cortex-queue-worker (picks up task)
  ↓
code-generator (specialized service)
  ↓
[Claude API generates code]
  ↓
Returns manifest YAML
  ↓
User receives generated code
```

### Example 3: YouTube video triggers autonomous improvement

```
YouTube: "Advanced Kubernetes Patterns" video
  ↓
youtube-ingestion (hourly cron)
  ↓
[Fetches transcript, analyzes with Claude]
  ↓
Generates 25 improvements with relevance scores
  ↓
redis-queue:improvements:raw (sorted set)
  ↓
school-coordinator (monitors queue)
  ↓
moe-router (routes to Architecture Expert - Opus 4.5)
  ↓
Expert evaluates: feasibility=high, impact=medium, priority=high
  ↓
redis-queue:improvements:categorized
  ↓
rag-validator
  ├─ Searches cortex-docs (no conflicts found)
  ├─ Searches cortex-gitops (not already implemented)
  └─ Searches qdrant (no similar improvements)
  ↓
redis-queue:improvements:validated
  ↓
Auto-approval gate (relevance 95% ≥ 90% ✅)
  ↓
redis-queue:improvements:approved
  ↓
implementation-worker (generates manifest)
  ↓
Git commit to cortex-gitops
  ↓
Push to GitHub
  ↓
ArgoCD detects change (within 3 min)
  ↓
Auto-syncs to cluster
  ↓
New Deployment created
  ↓
redis-queue:improvements:deployed
  ↓
health-monitor (watches for 5 minutes)
  ├─ Checks pod status every 10s
  ├─ Queries Prometheus metrics
  ├─ Scans logs for errors
  └─ Tests dependencies
  ↓
All checks pass ✅
  ↓
redis-queue:improvements:verified
  ↓
Improvement successfully implemented!
```

---

**Status**: Comprehensive visual flow as of 2026-01-15
**Note**: Cortex School pipeline partially active (coordinator + health-monitor running)
