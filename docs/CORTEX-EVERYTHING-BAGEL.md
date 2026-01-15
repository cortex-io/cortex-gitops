# Cortex: The Everything Bagel 🥯

**Complete System Architecture Map**
**Date**: 2026-01-15
**Status**: Comprehensive inventory of all Cortex components

---

## Table of Contents

1. [Local Machine Components](#local-machine-components)
2. [K3s Cluster - Core Infrastructure](#k3s-cluster---core-infrastructure)
3. [K3s Cluster - All Namespaces](#k3s-cluster---all-namespaces)
4. [MCP Servers](#mcp-servers)
5. [External Services](#external-services)
6. [Data Flow Architecture](#data-flow-architecture)
7. [Network Architecture](#network-architecture)
8. [GitOps Repositories](#gitops-repositories)

---

## Local Machine Components

### Claude Desktop App
**Location**: `/Applications/Claude.app`
**Process**: Running (PID 16425)
**Memory**: ~128MB
**Purpose**: Primary AI interface

**MCP Connection**: Connected to Cortex Desktop MCP at `http://10.88.145.216:8765`
- Uses Anthropic API key ending in `...oxQ-q0zTEgAA`
- Multiple MCP server processes running via Node.js

### Claude Code (CLI)
**Process**: Running (PID 37996, 74596)
**Memory**: ~456MB (active session)
**Purpose**: Terminal-based AI development interface
**Working Directory**: `~/Projects/cortex-gitops`

### Local MCP Clients
**Type**: Node.js MCP client processes
**Count**: 8 active instances
**Connection**: HTTP to cortex-desktop-mcp service
**Protocol**: JSON-RPC 2.0

### kubectl Port Forwards
- **Langflow**: `localhost:17860 → langflow.cortex-system:7860`

---

## K3s Cluster - Core Infrastructure

### Cluster Details
- **Nodes**: 7 total
  - 3 master nodes (k3s-master01/02/03): `10.88.145.190/193/196`
  - 4 worker nodes (k3s-worker01-04): `10.88.145.191/192/194/195`
- **Version**: K3s v1.33.6+k3s1
- **OS**: Ubuntu 24.04.3 LTS
- **Container Runtime**: containerd 2.1.5
- **Ingress**: Traefik LoadBalancer at `10.88.145.200`

---

## K3s Cluster - All Namespaces

### 1. cortex-system (Core Infrastructure)

**Purpose**: Central nervous system of Cortex

#### Core Services
- **cortex-orchestrator** (1/1)
  - Main API orchestrator
  - Exposed: ClusterIP `10.43.28.99:8080`
  - Metrics: `:9090`
  - Handles task routing, self-healing, queue management

- **cortex-resource-manager** (1/1)
  - LoadBalancer: `10.88.145.204:8080`
  - Resource monitoring and allocation
  - Status: 1 replica crashing (backup running)

- **coordinator-master** (1/1)
  - Service: `10.43.123.134:8080`
  - Coordinates multi-agent workflows

#### Databases
- **postgres-postgresql** (StatefulSet 1/1)
  - ClusterIP: `10.43.135.206:5432`
  - Headless service for clustering
  - PostgreSQL exporter on `:9187`
  - pgAdmin UI available
  - Daily backups via CronJob

- **redis-master** (StatefulSet 1/1)
  - ClusterIP: `10.43.48.239:6379`
  - Replicas: 0/0 (single master)
  - Headless service for failover

#### MCP Servers (Model Context Protocol)
- **cortex-mcp-server** (1/1)
  - Ports: `3000` (MCP), `8080` (HTTP)
  - Ingress: `cortex-mcp.ry-ops.dev`
  - Main Cortex MCP interface

- **sandfly-mcp-server** (1/1)
  - Port: `3000`
  - Security monitoring integration
  - Sandfly web UI: `10.43.85.76:443`

- **proxmox-mcp-server** (1/1)
  - Port: `3000`
  - Proxmox VE infrastructure management

- **unifi-mcp-server** (1/1)
  - Port: `3000`
  - UniFi network device management

- **kubernetes-mcp-server** (1/1)
  - Port: `3001`
  - K8s cluster management via MCP

- **checkmk-mcp-server** (1/1)
  - Port: `3000`
  - CheckMK monitoring integration

- **github-security-mcp-server** (1/1)
  - Port: `3003`
  - GitHub security scanning

- **n8n-mcp-server** (1/1)
  - Port: `3002`
  - n8n workflow automation

- **cloudflare-mcp-server** (0/1 CrashLoopBackOff)
  - Port: `3000`
  - Cloudflare DNS/security management
  - Status: Currently failing

- **langflow-chat-mcp-server** (0/1 CreateContainerConfigError)
  - Port: `3000`
  - Langflow chat integration
  - Status: Configuration issue

#### AI/ML Services
- **langflow** (1/1)
  - ClusterIP: `10.43.37.64:7860`
  - Ingress: `langflow.ry-ops.dev`
  - Visual workflow builder for AI apps

- **docling-service** (1/1)
  - ClusterIP: `10.43.175.238:8000`
  - Document processing with structure awareness

#### Development Tools
- **cicd-master** (1/1)
  - Service: `10.43.199.106:8080`
  - CI/CD orchestration

- **development-master** (1/1)
  - Service: `10.43.164.140:8080`
  - Development environment coordination

- **security-master** (1/1)
  - Service: `10.43.173.115:8080`
  - Security policy management

#### Infrastructure
- **cortex-live-cli** (DaemonSet 5/7)
  - Runs on 5 worker nodes
  - Real-time cluster monitoring
  - 2 nodes failing (ImagePullBackOff)

- **auto-fix-daemon** (1/1)
  - Automatic issue remediation

#### Jobs
- **postgres-backup** (CronJob: daily 2am)
- **infrastructure-deploy-to-masters** (Completed)
- **fix-cortex-live-rbac** (Completed)

---

### 2. cortex (Main Application Namespace)

**Purpose**: Primary Cortex application services

#### Core Application Services
- **cortex-orchestrator** (1/1)
  - ClusterIP: `10.43.234.57:8000`
  - API endpoint
  - Ingress: `cortex-api.ry-ops.dev`

- **cortex-queue-worker** (2/2 with HPA)
  - Processes background tasks
  - HPA: 2-25 replicas based on CPU (70%) and memory (80%)
  - Current: 2% CPU, 10% memory

- **cortex-desktop-mcp** (1/1)
  - LoadBalancer: `10.88.145.216:8765`
  - Desktop MCP server
  - Connects Claude Desktop app to cluster

#### Cost & Billing
- **cost-tracker** (1/1)
  - ClusterIP: `10.43.187.201:8080`
  - Tracks API usage and costs

- **model-router** (1/1)
  - ClusterIP: `10.43.52.140:8080`
  - Routes requests to appropriate AI models

#### YouTube Intelligence Pipeline
- **youtube-ingestion** (1/1)
  - ClusterIP: `10.43.119.1:8080`
  - Ingests YouTube videos
  - Generates improvement proposals
  - Feeds cortex-school

- **youtube-channel-intelligence** (1/1)
  - ClusterIP: `10.43.126.218:8081`
  - Channel analytics and insights

#### Infrastructure
- **redis-queue** (1/1)
  - ClusterIP: `10.43.10.63:6379`
  - Task queue (not redis.cortex!)

#### Documentation
- **documentation-master** (CronJob: daily 2am)
  - Crawls documentation sources
  - Indexes knowledge base

#### Shadow AI Detection
- **shadow-ai-scanner** (CronJob: daily 2am)
  - Scans for unauthorized AI usage

---

### 3. cortex-school (Autonomous Learning System) ✨ NEW

**Purpose**: Self-teaching infrastructure from YouTube content

#### Services
- **school-coordinator** (1/1) ✅
  - ClusterIP: `10.43.53.15:8080`
  - Orchestrates learning pipeline
  - Status: Running and healthy

- **health-monitor** (1/1) ✅
  - ClusterIP: `10.43.64.197:8080`
  - Monitors deployments
  - Triggers automatic rollbacks
  - Status: Running and healthy

- **moe-router** (0/1 Pending)
  - ClusterIP: `10.43.239.131:8080`
  - Routes to 6 expert agents
  - Status: Insufficient memory

- **rag-validator** (0/2 Pending)
  - ClusterIP: `10.43.120.189:8080`
  - Validates against existing infra
  - Status: Insufficient memory

- **implementation-workers** (0/3 Pending)
  - ClusterIP: `10.43.191.79:8080`
  - Generates GitOps manifests
  - Status: Insufficient memory

- **qdrant** (StatefulSet 0/1 Pending)
  - ClusterIP: `10.43.56.55:6333/6334`
  - Vector database for RAG
  - Storage: 20Gi Longhorn
  - Status: Insufficient memory

**Pipeline Flow**:
```
YouTube → Coordinator → MoE Experts → RAG Validation → Auto-Approve (≥90%) →
Workers → Git Commit → ArgoCD → Health Monitor → Verify/Rollback
```

**Secrets**:
- `anthropic-api-key` ✅
- `openai-api-key` ✅
- `github-token` ✅

---

### 4. cortex-chat (Chat Interface)

**Purpose**: Web-based chat interface for Cortex

#### Services
- **cortex-chat** (1/1)
  - Frontend: LoadBalancer `10.88.145.210:80`
  - Ingress: `chat.ry-ops.dev`
  - Chat UI

- **cortex-chat-backend-simple** (1/1)
  - ClusterIP: `10.43.34.83:8080`
  - Backend API

- **cortex-chat-proxy** (1/1)
  - ClusterIP: `10.43.73.13:8080`
  - Proxy for API requests

- **docker-registry** (1/1)
  - ClusterIP: `10.43.170.72:5000`
  - Local container registry

- **redis** (1/1)
  - ClusterIP: `10.43.210.189:6379`
  - Session storage

- **grafana-pdf-service** (1/1)
  - ClusterIP: `10.43.135.179:3001`
  - PDF report generation
  - Ingress: `cortex-reports.ry-ops.dev`

---

### 5. cortex-knowledge (Knowledge Graph & Analytics)

**Purpose**: Knowledge extraction, graph storage, and intelligence

#### Knowledge Services
- **knowledge-graph-api** (2/2)
  - ClusterIP: `10.43.175.202:8000`
  - Metrics: `:9091`
  - GraphQL API

- **knowledge-extractor** (standalone, not deployed)
  - Port: `8080`, metrics `:9090`
  - Extracts knowledge from sources

- **improvement-detector** (1/1)
  - ClusterIP: `10.43.47.228:8080`
  - Metrics: `:9092`
  - Detects improvement opportunities

- **value-stream-optimizer** (standalone)
  - Port: `8000`, metrics `:9093`
  - Optimizes workflows

#### Databases
- **knowledge-mongodb** (StatefulSet 1/1)
  - Headless: `None:27017`
  - Document storage

- **knowledge-elasticsearch** (StatefulSet 0/1)
  - Headless: `None:9200/9300`
  - Full-text search
  - Status: Not running

- **knowledge-graph** (Neo4j, standalone)
  - Headless: `None:7474/7687`
  - Graph database

#### Observability
- **phoenix** (1/1)
  - ClusterIP: `10.43.24.250:6006`
  - Ports: `:4317` (OTLP), `:9090` (metrics)
  - Ingress: `observability.ry-ops.dev`
  - LLM observability platform

- **knowledge-dashboard** (1/1)
  - LoadBalancer: `10.88.145.208:80`
  - Web dashboard

#### Documentation
- **outline** (standalone)
  - ClusterIP: `10.43.238.193:3000`
  - Wiki/documentation platform
  - Init job running

---

### 6. cortex-security (Security Monitoring)

**Purpose**: Security scanning, intrusion detection, compliance

#### Services
- **falco-falcosidekick** (1/1)
  - ClusterIP: `10.43.216.93:2801/2810`
  - Runtime security forwarding

- **falco-falcosidekick-ui** (1/1)
  - ClusterIP: `10.43.123.37:2802`
  - Security alerts dashboard

#### Jobs
- **trivy-cluster-scan** (CronJob: daily 2am)
  - Running: 3d18h
  - Container vulnerability scanning

---

### 7. cortex-cicd (CI/CD Pipeline)

**Purpose**: Continuous integration and deployment

#### Services
- **el-github-webhook-listener** (1/1)
  - ClusterIP: `10.43.44.101:8080`
  - Ingress: `tekton-webhooks.cortex.local`
  - GitHub webhook receiver
  - EventListener for Tekton

#### Status
- 330 restarts over 5 days
- Currently running

---

### 8. cortex-dev (Development Tools)

**Purpose**: Developer tooling and utilities

#### Services
- **code-generator** (1/1)
  - ClusterIP: `10.43.109.65:8080`
  - AI-powered code generation

- **issue-parser** (1/1)
  - ClusterIP: `10.43.130.170:8080`
  - GitHub issue analysis

- **repo-context** (standalone)
  - ClusterIP: `10.43.177.237:8080`
  - Repository context analysis

- **redis-service** (1/1)
  - ClusterIP: `10.43.79.194:6379`
  - Dev environment cache

---

### 9. cortex-csaf (Security Advisory Framework)

**Purpose**: CSAF (Common Security Advisory Framework) processing

#### Services
- **csaf-runtime** (2/2 with HPA)
  - ClusterIP: `10.43.119.102:8080`
  - HPA: 2-10 replicas (CPU 70%, memory 80%)
  - Current: 0% CPU, 7% memory

- **csaf-registry** (2/2)
  - ClusterIP: `10.43.143.130:8080`
  - Advisory registry

- **csaf-postgres** (1/1)
  - ClusterIP: `10.43.46.169:5432`
  - Advisory database

- **csaf-redis** (1/1)
  - ClusterIP: `10.43.245.27:6379`
  - Cache layer

- **csaf-correlator** (standalone)
  - ClusterIP: `10.43.188.179:8080`
  - Correlates security advisories

- **csaf-prompt-engine** (standalone)
  - ClusterIP: `10.43.174.80:8080`
  - AI-powered advisory analysis

#### Jobs
- **csaf-seed-apps-loader** (Completed 3d13h ago)

---

### 10. cortex-live (Real-time Monitoring)

**Purpose**: Live system monitoring and dashboards

#### Services
- **cortex-live** (1/1)
  - ClusterIP: Running
  - Real-time dashboard

#### Jobs
- **cortex-live-builder** (Error)
  - Image build job failed

---

### 11. cortex-metrics (Metrics Collection)

**Purpose**: Custom metrics collection and export

#### Services
- **cortex-metrics-api** (2/2)
  - LoadBalancer: `10.88.145.209:8080`
  - Metrics API

- **cortex-metrics-exporter** (0/1 Error)
  - ClusterIP: `10.43.177.224:9134`
  - Prometheus exporter
  - Status: 381 errors

- **cortex-metrics-collector** (0/1 CrashLoopBackOff)
  - Status: 372 crashes

- **cortex-report-generator** (0/1 CrashLoopBackOff)
  - Status: 381 crashes

**Status**: Namespace has issues, services crashing

---

### 12. cortex-ai-infra (AI Infrastructure Monitoring)

**Purpose**: AI-specific infrastructure monitoring

#### Services
- **network-fabric-monitor** (DaemonSet 5/7)
  - Running on 5 nodes
  - 2 nodes: ImagePullBackOff
  - Monitors network performance

---

### 13. cortex-itil (IT Service Management)

**Purpose**: ITIL-compliant service management

#### Services
- **incident-swarming** (standalone)
  - ClusterIP: `10.43.34.2:8080`
  - Collaborative incident resolution

- **event-correlation** (standalone)
  - ClusterIP: `10.43.169.27:8081`
  - Correlates related events

- **intelligent-alerting** (standalone)
  - ClusterIP: `10.43.38.114:8082`
  - Smart alert routing

- **problem-identification** (standalone)
  - ClusterIP: `10.43.223.42:8083`
  - Root cause analysis

- **kedb** (Knowledge Error Database) (standalone)
  - ClusterIP: `10.43.248.182:8084`
  - Known error database

---

### 14. cortex-itil-stream2 (ITIL Analytics)

**Purpose**: Advanced ITIL analytics

#### Services
- **sla-predictor** (standalone)
  - ClusterIP: `10.43.10.7:8000`
  - Predicts SLA violations

- **business-metrics-collector** (standalone)
  - ClusterIP: `10.43.106.61:8001`
  - Collects business KPIs

- **availability-risk-engine** (standalone)
  - ClusterIP: `10.43.234.252:8002`
  - Risk assessment

---

### 15. cortex-change-mgmt (Change Management)

**Purpose**: Change approval and tracking

#### Services
- **change-manager** (standalone)
  - ClusterIP: `10.43.83.16:8080`
  - Change request workflow

---

### 16. cortex-lifecycle (Lifecycle Management)

**Purpose**: Service lifecycle auditing

#### Jobs
- **lifecycle-auditor** (CronJob: every 6 hours)
  - Last run: 5h30m ago
  - Audits service states

---

### 17. cortex-control-plane (Control Plane Management)

**Purpose**: Kubernetes control plane monitoring

#### Services
- **control-plane** (1/1)
  - ClusterIP: `10.43.155.101:8080`
  - Control plane health monitoring

---

### 18. cortex-tui (Terminal UI)

**Purpose**: Terminal-based monitoring interface

#### Status
- All replicas at 0
- Not currently active

---

### 19. cortex-governance (Policy & Compliance)

**Purpose**: Governance policies and compliance checking

**Status**: Namespace exists but no active services

---

### 20. cortex-orchestration (Workflow Orchestration)

**Purpose**: Multi-service workflow orchestration

**Status**: Namespace exists but no active services

---

### 21. cortex-autonomous (Autonomous Operations)

**Purpose**: Self-driving infrastructure operations

**Status**: Namespace exists but no active services

---

### 22. cortex-service-desk (Service Desk)

**Purpose**: IT service desk portal

#### Ingress
- Hosts: `service-desk.cortex.local`, `api.service-desk.cortex.local`, `fulfillment.service-desk.cortex.local`

**Status**: Namespace exists

---

### 23. cortex-standards (Standards & Best Practices)

**Purpose**: Standards enforcement and best practice checking

**Status**: Namespace exists (32h old)

---

## MCP Servers

### Currently Running (9 servers)

1. **cortex-mcp-server** (`cortex-system`)
   - Main Cortex MCP interface
   - Exposed: `cortex-mcp.ry-ops.dev`
   - Tools: Task management, queue operations, cluster queries

2. **sandfly-mcp-server** (`cortex-system`)
   - Security monitoring (Sandfly integration)
   - EDR/threat detection

3. **proxmox-mcp-server** (`cortex-system`)
   - Proxmox VE management
   - VM/Container operations

4. **unifi-mcp-server** (`cortex-system`)
   - UniFi network device management
   - Network monitoring

5. **kubernetes-mcp-server** (`cortex-system`)
   - K8s cluster operations
   - Resource management

6. **checkmk-mcp-server** (`cortex-system`)
   - CheckMK monitoring integration
   - Metrics collection

7. **github-security-mcp-server** (`cortex-system`)
   - GitHub security scanning
   - Dependabot alerts

8. **n8n-mcp-server** (`cortex-system`)
   - n8n workflow automation
   - Integration platform

9. **cortex-desktop-mcp** (`cortex`)
   - Desktop client MCP bridge
   - Exposed: `10.88.145.216:8765`

### Failing (2 servers)

10. **cloudflare-mcp-server** (`cortex-system`)
    - Status: CrashLoopBackOff
    - Purpose: Cloudflare DNS/security

11. **langflow-chat-mcp-server** (`cortex-system`)
    - Status: CreateContainerConfigError
    - Purpose: Langflow chat integration

---

## External Services

### GitHub Repositories
- **cortex-gitops**: `https://github.com/ry-ops/cortex-gitops`
  - Kubernetes manifests
  - ArgoCD Applications
  - 121 YAML files

- **cortex-platform**: `https://github.com/ry-ops/cortex-platform`
  - Application source code
  - 10,661 files
  - Services, libraries, coordination

- **cortex-docs**: `https://github.com/ry-ops/cortex-docs`
  - Architecture documentation
  - Knowledge base

- **cortex-k3s**: `https://github.com/ry-ops/cortex-k3s`
  - K3s cluster documentation

### External APIs
- **Anthropic API**: Claude models (Opus 4.5, Sonnet 4.5, Haiku 4)
- **OpenAI API**: Embeddings (text-embedding-3-large)
- **GitHub API**: Repository operations, webhooks
- **Sandfly API**: `10.88.140.176` (security monitoring)

### DNS
- **Public domains** (via Traefik + cert-manager):
  - `chat.ry-ops.dev`
  - `cortex-api.ry-ops.dev`
  - `cortex-mcp.ry-ops.dev`
  - `langflow.ry-ops.dev`
  - `cortex-reports.ry-ops.dev`
  - `observability.ry-ops.dev`
  - `sandfly.ry-ops.dev`

- **Internal domains**:
  - `service-desk.cortex.local`
  - `tekton.cortex.local`
  - `linkerd.cortex.local`

---

## Data Flow Architecture

### 1. User Interaction Flow

```
User (Local) → Claude Desktop → MCP Client → cortex-desktop-mcp (10.88.145.216:8765)
                                                    ↓
                                           cortex-mcp-server
                                                    ↓
                                         cortex-orchestrator (cortex-system)
                                                    ↓
                                         [Queue via redis-master]
                                                    ↓
                                         cortex-queue-worker (2 replicas)
                                                    ↓
                                         [Execute task with relevant MCP servers]
```

### 2. YouTube Learning Flow

```
YouTube Video → youtube-ingestion:8080
                       ↓
                [Extract transcript & analyze]
                       ↓
                [Generate 25 improvements]
                       ↓
                redis-queue:improvements:raw
                       ↓
            school-coordinator (monitors queue)
                       ↓
            [Routes to moe-router]
                       ↓
            [6 Expert Agents evaluate]
                       ↓
            redis-queue:improvements:categorized
                       ↓
            rag-validator (checks conflicts)
                       ↓
            [Searches: cortex-docs, cortex-gitops, past improvements]
                       ↓
            redis-queue:improvements:validated
                       ↓
            [Auto-approve if relevance ≥ 90%]
                       ↓
            redis-queue:improvements:approved
                       ↓
            implementation-workers (generate manifests)
                       ↓
            [Git commit to cortex-gitops]
                       ↓
            GitHub (cortex-gitops repo)
                       ↓
            ArgoCD (polls every 3 min)
                       ↓
            K8s Deployment
                       ↓
            health-monitor (5 min monitoring)
                       ↓
            [Success: redis-queue:improvements:verified]
            [Failure: git revert + redis-queue:improvements:failed]
```

### 3. Code Generation Flow

```
User Request → cortex-api (cortex-api.ry-ops.dev)
                     ↓
          cortex-orchestrator (cortex)
                     ↓
          code-generator (cortex-dev)
                     ↓
          [AI generates code]
                     ↓
          [Return to user]
```

### 4. Knowledge Graph Flow

```
Documentation Sources → documentation-master (CronJob)
                              ↓
                    knowledge-extractor
                              ↓
                    knowledge-graph (Neo4j)
                              ↓
                    knowledge-graph-api
                              ↓
                    knowledge-dashboard (UI)
```

---

## Network Architecture

### Load Balancers

**Traefik Ingress Controller**
- IP: `10.88.145.200`
- Ports: 80 (HTTP), 443 (HTTPS)
- TLS: cert-manager with Let's Encrypt

**Exposed LoadBalancers**:
1. `10.88.145.204` - cortex-resource-manager
2. `10.88.145.208` - knowledge-dashboard
3. `10.88.145.209` - cortex-metrics-api
4. `10.88.145.210` - cortex-chat-frontend
5. `10.88.145.216` - cortex-desktop-mcp

### Internal Service Mesh

**Linkerd** (service mesh)
- Dashboard: `linkerd.cortex.local`
- mTLS between services
- Traffic metrics

### Network Policies

**Active Namespaces with NetworkPolicies**:
- cortex-system
- cortex
- cortex-security

---

## GitOps Repositories

### Primary Repositories

#### cortex-gitops
**Location**: `~/Projects/cortex-gitops`
**GitHub**: `ry-ops/cortex-gitops`
**Purpose**: Single source of truth for Kubernetes manifests

**Structure**:
```
cortex-gitops/
├── apps/
│   ├── cortex-system/      (49 resources)
│   ├── cortex/             (16 resources)
│   ├── cortex-chat/        (17 resources)
│   ├── cortex-school/      (8 resources) ✨ NEW
│   ├── cortex-dev/         (8 resources)
│   ├── cortex-cicd/        (3 resources)
│   ├── cortex-security/    (12 resources)
│   └── cortex-knowledge/   (15 resources)
├── argocd-apps/            (7 Applications)
└── README.md
```

**ArgoCD Applications**: 7
- cortex-system
- cortex-core
- cortex-chat
- cortex-school ✨ NEW
- cortex-dev
- cortex-cicd
- cortex-security
- cortex-knowledge

**Total Resources Under GitOps**: 120+

#### cortex-platform
**Location**: `~/Projects/cortex-platform`
**GitHub**: `ry-ops/cortex-platform`
**Purpose**: Application source code

**Structure**:
```
cortex-platform/
├── services/
│   ├── coordinator/        ✨ NEW (cortex-school)
│   ├── moe-router/         ✨ NEW (cortex-school)
│   ├── rag-validator/      ✨ NEW (cortex-school)
│   ├── implementation-worker/ ✨ NEW (cortex-school)
│   ├── health-monitor/     ✨ NEW (cortex-school)
│   ├── mcp-servers/
│   ├── api/
│   ├── workers/
│   └── ...
├── lib/
├── coordination/
└── docs/
```

**Total Files**: 10,661

#### cortex-docs
**Location**: `~/Projects/cortex-docs`
**GitHub**: `ry-ops/cortex-docs`
**Purpose**: Architecture documentation

**Key Files**:
- `vault/architecture/cortex-online-school.md` (1,350 lines)
- Architecture diagrams
- Design decisions
- API documentation

---

## System Statistics

### Resource Totals
- **Namespaces**: 23 (22 cortex-*, 1 other)
- **Pods**: ~100+ running
- **Services**: ~80+
- **Deployments**: ~50+
- **StatefulSets**: ~8
- **DaemonSets**: ~2
- **CronJobs**: ~7
- **MCP Servers**: 11 (9 running, 2 failing)
- **Ingresses**: 15+
- **Load Balancers**: 5

### Memory Pressure
**Current Issue**: Cluster memory constraints
- 5 of 7 worker nodes reporting insufficient memory
- Cortex-school services pending due to memory
- Multiple services scaled down or crashing

**Affected**:
- cortex-school (moe-router, rag-validator, implementation-workers, qdrant)
- cortex-metrics (collector, exporter, report-generator)
- cortex-resource-manager (1 replica)
- cortex-ai-infra (2 network monitors)

### Health Summary
- **Healthy**: 70+ services
- **Pending**: 10+ services (memory)
- **CrashLoopBackOff**: 5 services
- **Failed/Error**: 3 services
- **Completed Jobs**: 30+

---

## Key Integration Points

### Local ↔ K3s
1. **Claude Desktop** → `cortex-desktop-mcp` (10.88.145.216:8765)
2. **kubectl** → K3s API (kubeconfig)
3. **Port forwards** → Various services (langflow, etc.)

### K3s ↔ External
1. **ArgoCD** → GitHub (cortex-gitops, cortex-platform, cortex-docs)
2. **cert-manager** → Let's Encrypt (TLS certificates)
3. **Services** → Anthropic API (Claude models)
4. **Services** → OpenAI API (embeddings)
5. **Services** → Sandfly API (security)

### Inter-Service Communication
1. **cortex-orchestrator** ↔ **redis-master** (task queue)
2. **youtube-ingestion** ↔ **redis-queue** (improvements queue)
3. **school-coordinator** ↔ **redis-queue** (pipeline stages)
4. **All services** ↔ **postgres-postgresql** (persistent data)
5. **MCP servers** ↔ **cortex-mcp-server** (tool routing)

---

## The Everything Bagel - Summary View

```
┌─────────────────────────────────────────────────────────────────┐
│                       YOUR LOCAL MACHINE                         │
│                                                                  │
│  Claude Desktop App ──MCP──> cortex-desktop-mcp (10.88.145.216) │
│  Claude Code CLI                                                 │
│  kubectl (K3s access)                                            │
│  Git repos: cortex-gitops, cortex-platform, cortex-docs         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    K3S CLUSTER (7 NODES)                         │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ CORE (cortex-system): 49 resources                      │   │
│  │ • cortex-orchestrator (main API)                        │   │
│  │ • 9 MCP servers (sandfly, proxmox, unifi, k8s, etc.)   │   │
│  │ • postgres, redis, langflow, docling                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ APPS (cortex): 16 resources                             │   │
│  │ • youtube-ingestion, cortex-orchestrator                │   │
│  │ • cost-tracker, model-router                            │   │
│  │ • cortex-desktop-mcp (LoadBalancer)                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ SCHOOL (cortex-school): 8 resources ✨ NEW              │   │
│  │ • coordinator, health-monitor (RUNNING)                 │   │
│  │ • moe-router, rag-validator, workers, qdrant (PENDING) │   │
│  │ → Autonomous learning from YouTube                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ UI (cortex-chat): 17 resources                          │   │
│  │ • Frontend (chat.ry-ops.dev)                            │   │
│  │ • Backend, proxy, registry                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ KNOWLEDGE (cortex-knowledge): 15 resources              │   │
│  │ • Neo4j graph, MongoDB, Elasticsearch                   │   │
│  │ • Phoenix observability, Outline wiki                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  + 18 more namespaces (security, dev, cicd, metrics, etc.)      │
│                                                                  │
│  TOTAL: 120+ managed resources, 100+ pods                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      EXTERNAL SERVICES                           │
│                                                                  │
│  • GitHub (cortex-gitops, cortex-platform, cortex-docs)         │
│  • Anthropic API (Claude models)                                │
│  • OpenAI API (embeddings)                                      │
│  • Sandfly Security                                             │
│  • Let's Encrypt (TLS)                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

**Status**: Comprehensive as of 2026-01-15
**Note**: cortex-school services partially deployed (2/9 pods running due to memory constraints)
