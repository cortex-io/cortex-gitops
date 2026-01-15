# Cortex: Roles & Responsibilities

**Complete Role Definition for Every Component**
**Date**: 2026-01-15

---

## Table of Contents

1. [Gateway & Interface Layer](#gateway--interface-layer)
2. [Orchestration & Coordination](#orchestration--coordination)
3. [MCP Servers](#mcp-servers)
4. [AI & Machine Learning Services](#ai--machine-learning-services)
5. [Autonomous Learning (Cortex School)](#autonomous-learning-cortex-school)
6. [Knowledge & Intelligence](#knowledge--intelligence)
7. [Development Tools](#development-tools)
8. [Security & Compliance](#security--compliance)
9. [Monitoring & Observability](#monitoring--observability)
10. [Data & Persistence](#data--persistence)
11. [Infrastructure & Platform](#infrastructure--platform)
12. [CI/CD & GitOps](#cicd--gitops)

---

## Gateway & Interface Layer

### cortex-desktop-mcp
**Namespace**: `cortex`
**Type**: LoadBalancer Service
**Exposed**: `10.88.145.216:8765`

**Role**: Desktop Client Bridge
**Responsibilities**:
- Bridge local Claude Desktop app to K8s cluster
- MCP protocol gateway (JSON-RPC 2.0)
- Authentication and authorization of local clients
- Request routing to cortex-mcp-server
- Response transformation and caching

**Dependencies**:
- cortex-mcp-server (routing)
- redis-master (session cache)

**Consumers**:
- Claude Desktop App (local machine)
- Custom MCP clients

---

### cortex-chat-frontend
**Namespace**: `cortex-chat`
**Type**: LoadBalancer Service
**Exposed**: `10.88.145.210:80`, `chat.ry-ops.dev`

**Role**: Web Chat Interface
**Responsibilities**:
- Serve web-based chat UI
- Handle user authentication
- WebSocket connections for real-time chat
- File upload handling
- Session management

**Dependencies**:
- cortex-chat-backend-simple (API)
- cortex-chat-proxy (reverse proxy)
- redis (sessions)

**Consumers**:
- Web browsers (users)

---

### cortex-chat-proxy
**Namespace**: `cortex-chat`
**Type**: ClusterIP Service

**Role**: API Reverse Proxy
**Responsibilities**:
- Rate limiting
- Request/response transformation
- Load balancing to backend
- TLS termination
- CORS handling

**Dependencies**:
- cortex-chat-backend-simple

**Consumers**:
- cortex-chat-frontend

---

## Orchestration & Coordination

### cortex-orchestrator (cortex-system)
**Namespace**: `cortex-system`
**Type**: ClusterIP Service
**Ports**: `8080` (API), `9090` (metrics)

**Role**: Central API Orchestrator
**Responsibilities**:
- Main API endpoint for all Cortex operations
- Multi-agent workflow orchestration
- Task routing and coordination
- Request validation and authentication
- Rate limiting and throttling
- Error handling and retry logic
- Metrics collection and reporting

**Dependencies**:
- redis-master (task queue)
- postgres-postgresql (state storage)
- All MCP servers (via cortex-mcp-server)

**Consumers**:
- cortex-mcp-server
- cortex-chat-backend
- Direct API clients

**Critical**: Yes - single point of orchestration

---

### cortex-orchestrator (cortex)
**Namespace**: `cortex`
**Type**: ClusterIP Service
**Port**: `8000`

**Role**: Application-Level Orchestrator
**Responsibilities**:
- Application-specific task coordination
- API endpoint management
- Service-to-service communication
- Request aggregation
- Response caching

**Dependencies**:
- redis-queue (task queue)
- Various application services

**Consumers**:
- Web interface
- API clients

---

### coordinator-master
**Namespace**: `cortex-system`
**Type**: ClusterIP Service

**Role**: Master Coordinator
**Responsibilities**:
- Coordinate multiple orchestrators
- Distributed task scheduling
- Failover and high availability
- Service discovery
- Health checking

**Dependencies**:
- redis-master
- cortex-orchestrator

**Consumers**:
- System-level services

---

### cortex-queue-worker
**Namespace**: `cortex`
**Type**: Deployment (2-25 replicas with HPA)
**Scaling**: CPU 70%, Memory 80%

**Role**: Background Task Processor
**Responsibilities**:
- Process tasks from redis-queue
- Execute long-running operations
- Handle async requests
- Retry failed tasks
- Report task status
- Auto-scale based on queue depth

**Dependencies**:
- redis-queue (task source)
- Specialized services (code-generator, issue-parser, etc.)

**Consumers**:
- Tasks queued by cortex-orchestrator

---

## MCP Servers

### cortex-mcp-server
**Namespace**: `cortex-system`
**Type**: ClusterIP Service
**Ports**: `3000` (MCP), `8080` (HTTP)
**Exposed**: `cortex-mcp.ry-ops.dev`

**Role**: Main MCP Router
**Responsibilities**:
- Route MCP tool calls to appropriate specialized servers
- Tool discovery and registration
- Context management across tool calls
- Authentication and authorization
- Rate limiting per client
- Logging and audit trail
- Error handling and fallback

**Tools Provided**:
- Task management
- Queue operations
- Cluster queries
- Service discovery

**Dependencies**:
- All specialized MCP servers
- cortex-orchestrator

**Consumers**:
- cortex-desktop-mcp
- Direct MCP clients

**Critical**: Yes - MCP routing hub

---

### sandfly-mcp-server
**Namespace**: `cortex-system`
**Type**: ClusterIP Service

**Role**: Security Monitoring Integration
**Responsibilities**:
- Query Sandfly API for security alerts
- List suspicious hosts and processes
- Trigger security scans
- Retrieve threat intelligence
- Manage security policies

**Tools Provided**:
- `sandfly_list_hosts` - List monitored hosts
- `sandfly_get_alerts` - Retrieve security alerts
- `sandfly_scan_host` - Trigger host scan
- `sandfly_quarantine` - Isolate compromised host

**Dependencies**:
- Sandfly API (`10.88.140.176:443`)

**Consumers**:
- cortex-mcp-server
- Security workflows

---

### proxmox-mcp-server
**Namespace**: `cortex-system`
**Type**: ClusterIP Service

**Role**: Infrastructure Management
**Responsibilities**:
- Manage Proxmox VE hosts
- Create/delete VMs and containers
- Monitor resource usage
- Handle backups and snapshots
- Network configuration

**Tools Provided**:
- `proxmox_list_vms` - List all VMs
- `proxmox_create_vm` - Create new VM
- `proxmox_start_vm` - Start VM
- `proxmox_stop_vm` - Stop VM
- `proxmox_snapshot` - Create snapshot

**Dependencies**:
- Proxmox VE API

**Consumers**:
- cortex-mcp-server
- Infrastructure workflows

---

### unifi-mcp-server
**Namespace**: `cortex-system`
**Type**: ClusterIP Service

**Role**: Network Device Management
**Responsibilities**:
- Manage UniFi network devices
- Monitor network traffic
- Configure VLANs and firewall rules
- Track client connections
- Performance monitoring

**Tools Provided**:
- `unifi_list_devices` - List network devices
- `unifi_get_clients` - List connected clients
- `unifi_block_client` - Block device
- `unifi_get_traffic` - Traffic statistics
- `unifi_configure_vlan` - VLAN configuration

**Dependencies**:
- UniFi Controller API

**Consumers**:
- cortex-mcp-server
- Network workflows

---

### kubernetes-mcp-server
**Namespace**: `cortex-system`
**Type**: ClusterIP Service
**Port**: `3001`

**Role**: Kubernetes Operations
**Responsibilities**:
- Execute kubectl commands
- Resource CRUD operations
- Log retrieval
- Pod exec/port-forward
- Cluster health checks

**Tools Provided**:
- `k8s_get_pods` - List pods
- `k8s_get_logs` - Retrieve logs
- `k8s_apply_manifest` - Apply YAML
- `k8s_delete_resource` - Delete resource
- `k8s_port_forward` - Port forward

**Dependencies**:
- K8s API (in-cluster)

**Consumers**:
- cortex-mcp-server
- DevOps workflows

---

### checkmk-mcp-server
**Namespace**: `cortex-system`
**Type**: ClusterIP Service

**Role**: Monitoring Integration
**Responsibilities**:
- Query CheckMK monitoring data
- Retrieve service status
- Acknowledge alerts
- Trigger checks
- Generate reports

**Tools Provided**:
- `checkmk_get_hosts` - List monitored hosts
- `checkmk_get_services` - Service status
- `checkmk_ack_problem` - Acknowledge alert
- `checkmk_trigger_check` - Force check

**Dependencies**:
- CheckMK API

**Consumers**:
- cortex-mcp-server
- Monitoring workflows

---

### github-security-mcp-server
**Namespace**: `cortex-system`
**Type**: ClusterIP Service
**Port**: `3003`

**Role**: GitHub Security Scanning
**Responsibilities**:
- Scan repositories for vulnerabilities
- Retrieve Dependabot alerts
- Manage security policies
- Track secret scanning alerts
- Code scanning results

**Tools Provided**:
- `github_list_vulns` - List vulnerabilities
- `github_get_dependabot` - Dependabot alerts
- `github_scan_secrets` - Secret scanning
- `github_code_scan` - Code analysis

**Dependencies**:
- GitHub API

**Consumers**:
- cortex-mcp-server
- Security workflows

---

### n8n-mcp-server
**Namespace**: `cortex-system`
**Type**: ClusterIP Service
**Port**: `3002`

**Role**: Workflow Automation
**Responsibilities**:
- Trigger n8n workflows
- Monitor workflow execution
- Manage workflow templates
- Handle webhook integrations

**Tools Provided**:
- `n8n_trigger_workflow` - Execute workflow
- `n8n_list_workflows` - List workflows
- `n8n_get_execution` - Execution status

**Dependencies**:
- n8n API

**Consumers**:
- cortex-mcp-server
- Automation workflows

---

### cloudflare-mcp-server
**Namespace**: `cortex-system`
**Type**: ClusterIP Service
**Status**: CrashLoopBackOff ❌

**Role**: DNS & CDN Management
**Responsibilities** (when working):
- Manage Cloudflare DNS records
- Configure WAF rules
- Purge CDN cache
- Monitor traffic patterns

**Tools Provided**:
- `cloudflare_add_record` - Add DNS record
- `cloudflare_update_waf` - Configure WAF
- `cloudflare_purge_cache` - Clear cache

**Status**: Currently failing, needs investigation

---

### langflow-chat-mcp-server
**Namespace**: `cortex-system`
**Type**: ClusterIP Service
**Status**: CreateContainerConfigError ❌

**Role**: Langflow Chat Integration
**Responsibilities** (when working):
- Execute Langflow chat workflows
- Manage conversation context
- Handle file uploads

**Status**: Configuration issue, needs fixing

---

## AI & Machine Learning Services

### langflow
**Namespace**: `cortex-system`
**Type**: ClusterIP Service
**Port**: `7860`
**Exposed**: `langflow.ry-ops.dev`

**Role**: Visual AI Workflow Builder
**Responsibilities**:
- Visual flow-based AI app development
- Drag-and-drop LLM chains
- Integration with multiple AI providers
- RAG (Retrieval Augmented Generation) workflows
- Vector database integration
- Conversation memory management

**Dependencies**:
- postgres-postgresql (workflow storage)
- redis-master (cache)

**Consumers**:
- Developers (web UI)
- langflow-chat-mcp-server

---

### docling-service
**Namespace**: `cortex-system`
**Type**: ClusterIP Service
**Port**: `8000`

**Role**: Structure-Aware Document Processing
**Responsibilities**:
- Extract structure from documents (PDF, DOCX, etc.)
- Preserve semantic hierarchies
- Generate structured chunks for RAG
- Table extraction and parsing
- Image caption generation
- Metadata extraction

**Dependencies**:
- None (standalone service)

**Consumers**:
- knowledge-extractor
- RAG workflows
- Documentation processing

---

### model-router
**Namespace**: `cortex`
**Type**: ClusterIP Service

**Role**: AI Model Selection & Routing
**Responsibilities**:
- Route requests to appropriate AI model
- Load balancing across model providers
- Cost optimization (model selection)
- Fallback handling
- Token counting and budgeting

**Supported Models**:
- Claude (Opus 4.5, Sonnet 4.5, Haiku 4)
- OpenAI (GPT-4, GPT-3.5)
- Local models (if configured)

**Dependencies**:
- Anthropic API
- OpenAI API
- cost-tracker

**Consumers**:
- cortex-orchestrator
- All AI-powered services

---

### cost-tracker
**Namespace**: `cortex`
**Type**: ClusterIP Service

**Role**: API Usage & Cost Tracking
**Responsibilities**:
- Track API calls and token usage
- Calculate costs per provider
- Budget alerts and limits
- Usage analytics and reporting
- Cost optimization recommendations

**Dependencies**:
- postgres-postgresql (usage logs)

**Consumers**:
- model-router
- cortex-orchestrator
- Billing reports

---

## Autonomous Learning (Cortex School)

### youtube-ingestion
**Namespace**: `cortex`
**Type**: ClusterIP Service
**Cron**: Hourly

**Role**: YouTube Content Ingestion
**Responsibilities**:
- Fetch YouTube videos from subscribed channels
- Extract transcripts using YouTube API
- Analyze content with Claude
- Identify Cortex-relevant improvements
- Generate 25 improvement proposals per video
- Assign relevance scores (0.0-1.0)
- Categorize improvements (architecture, integration, security, etc.)
- Push to redis-queue:improvements:raw

**Dependencies**:
- YouTube API
- Anthropic API (Claude)
- redis-queue

**Consumers**:
- school-coordinator

**Output Format**:
```json
{
  "video_id": "rrQHnibpXX8",
  "title": "Video title",
  "relevance": 0.95,
  "category": "architecture",
  "type": "pattern",
  "description": "Brief description",
  "implementation_notes": "Detailed implementation..."
}
```

---

### school-coordinator
**Namespace**: `cortex-school`
**Type**: ClusterIP Service
**Status**: 1/1 Running ✅

**Role**: Learning Pipeline Orchestrator
**Responsibilities**:
- Monitor redis-queue:improvements:raw
- Coordinate MoE routing
- Manage RAG validation
- Apply auto-approval logic (≥90% threshold)
- Move improvements through pipeline stages
- Track improvement status
- Provide pipeline status API
- Handle override flags (emergency stop/approve all)

**Pipeline Stages**:
1. raw → moe-router → categorized
2. categorized → rag-validator → validated
3. validated → auto-approval → approved/pending_review
4. approved → implementation-workers → deployed
5. deployed → health-monitor → verified/failed

**Dependencies**:
- redis-queue (all stages)
- moe-router
- rag-validator

**Consumers**:
- Pipeline monitoring
- Improvement status queries

**Critical**: Yes - pipeline orchestrator

---

### moe-router
**Namespace**: `cortex-school`
**Type**: ClusterIP Service
**Status**: 0/1 Pending ⏳ (insufficient memory)

**Role**: Mixture of Experts Router
**Responsibilities**:
- Route improvements to specialized expert agents
- Load balance across experts
- LLM-D coordination for distributed inference
- Prefix caching for similar improvements
- Expert evaluation aggregation

**6 Expert Agents**:
1. **Architecture Expert** (Claude Opus 4.5)
   - System design patterns
   - Microservice architectures
   - Scalability strategies

2. **Integration Expert** (Claude Sonnet 4.5)
   - Third-party tools and APIs
   - Integration patterns
   - Data flow design

3. **Security Expert** (Claude Opus 4.5)
   - Authentication & authorization
   - Encryption strategies
   - Compliance requirements

4. **Database Expert** (Claude Sonnet 4.5)
   - Schema design
   - Migrations
   - Query optimization

5. **Networking Expert** (Claude Sonnet 4.5)
   - Ingress configuration
   - Service mesh
   - Load balancing

6. **Monitoring Expert** (Claude Haiku 4)
   - Observability patterns
   - Dashboard design
   - Alert configuration

**Expert Evaluation Output**:
- Feasibility (high/medium/low)
- Impact (high/medium/low)
- Risks (list)
- Effort (high/medium/low)
- Priority (high/medium/low)
- Recommendations
- Dependencies

**Dependencies**:
- Anthropic API
- redis-queue

**Consumers**:
- school-coordinator

---

### rag-validator
**Namespace**: `cortex-school`
**Type**: ClusterIP Service (2 replicas)
**Status**: 0/2 Pending ⏳ (insufficient memory)

**Role**: Conflict Detection via RAG
**Responsibilities**:
- Validate improvements against existing infrastructure
- Search cortex-docs for architectural conflicts
- Search cortex-gitops for duplicate implementations
- Search qdrant for similar past improvements
- Check dependency availability
- Verify cluster capacity
- Generate validation report

**Search Corpus**:
- cortex-docs (cloned in init container)
- cortex-gitops (cloned in init container)
- qdrant:past-improvements (vector database)

**Validation Checks**:
- ✅ Not already implemented
- ✅ No architectural conflicts
- ✅ Dependencies available
- ✅ Cluster has capacity
- ✅ No similar failed improvements

**Technologies**:
- Qdrant (vector database)
- OpenAI text-embedding-3-large (embeddings)
- Structure-aware chunking via docling

**Dependencies**:
- qdrant (vector store)
- OpenAI API (embeddings)
- Git repos (cortex-docs, cortex-gitops)

**Consumers**:
- school-coordinator

---

### qdrant
**Namespace**: `cortex-school`
**Type**: StatefulSet (0/1)
**Status**: Pending ⏳ (insufficient memory)
**Storage**: 20Gi Longhorn PVC

**Role**: Vector Database for RAG
**Responsibilities**:
- Store embeddings for all documentation
- Store embeddings for all manifests
- Store embeddings for past improvements
- Fast similarity search
- Hybrid search (vector + keyword)

**Collections**:
- `cortex-docs` - Documentation embeddings
- `cortex-gitops` - Manifest embeddings
- `past-improvements` - Historical improvement embeddings

**Dependencies**:
- Longhorn (storage)

**Consumers**:
- rag-validator

---

### implementation-workers
**Namespace**: `cortex-school`
**Type**: Deployment (3 replicas)
**Status**: 0/3 Pending ⏳ (insufficient memory)

**Role**: GitOps Manifest Generator
**Responsibilities**:
- Pick approved improvements from redis-queue
- Generate appropriate Kubernetes manifests
- Specialized workers by improvement type:
  - Architecture: Deployments, StatefulSets, ConfigMaps
  - Integration: Services, Ingress, MCP servers
  - Security: RBAC, NetworkPolicies, Secrets
  - Database: Schema migrations, backup jobs
  - Monitoring: Grafana dashboards, Prometheus rules
- Create detailed Git commit message
- Push to cortex-gitops repository
- Update improvement status to "deployed"

**RBAC Permissions**:
- Read: pods, services, configmaps, secrets, deployments, statefulsets
- Patch: ArgoCD Applications

**Dependencies**:
- redis-queue
- GitHub API (push commits)
- Kubernetes API (read resources)

**Consumers**:
- ArgoCD (syncs commits)

---

### health-monitor
**Namespace**: `cortex-school`
**Type**: Deployment (1 replica)
**Status**: 1/1 Running ✅

**Role**: Deployment Health Verification & Rollback
**Responsibilities**:
- Monitor redis-queue:improvements:deployed
- Track deployments for 5 minutes post-deploy
- Check pod status every 10 seconds
- Query Prometheus for metrics:
  - Error rate (<1% threshold)
  - Latency (<2x baseline)
- Scan logs for ERROR/FATAL/panic
- Test dependency connectivity
- Trigger automatic rollback on failure:
  1. git revert <commit>
  2. Push rollback commit
  3. Force ArgoCD sync
  4. Wait 30s for rollback
  5. Verify system healthy
  6. Log failure details
  7. Move to improvements:failed

**Health Check Criteria**:
- ✅ All pods Running
- ✅ All readiness probes passing
- ✅ Error rate <1%
- ✅ Latency <2x baseline
- ✅ No ERROR/FATAL in logs
- ✅ Dependencies reachable

**RBAC Permissions**:
- Read: pods, logs, events, services, deployments, statefulsets
- Patch: ArgoCD Applications

**Dependencies**:
- redis-queue
- Kubernetes API
- Prometheus
- GitHub API (rollback)

**Consumers**:
- Pipeline monitoring

**Critical**: Yes - ensures system stability

---

## Knowledge & Intelligence

### knowledge-extractor
**Namespace**: `cortex-knowledge`
**Type**: Standalone (not currently deployed)

**Role**: Knowledge Extraction from Sources
**Responsibilities**:
- Extract knowledge from documentation
- Parse API specifications
- Analyze code repositories
- Extract entities and relationships
- Generate knowledge graph nodes
- Create vector embeddings

**Dependencies**:
- docling-service
- knowledge-graph (Neo4j)
- knowledge-mongodb

**Consumers**:
- documentation-master (cron job)

---

### knowledge-graph-api
**Namespace**: `cortex-knowledge`
**Type**: ClusterIP Service (2 replicas)
**Ports**: `8000` (API), `9091` (metrics)

**Role**: Knowledge Graph Query API
**Responsibilities**:
- GraphQL API for knowledge graph
- Cypher query execution
- Relationship traversal
- Entity search
- Knowledge recommendations
- Graph analytics

**Dependencies**:
- knowledge-graph (Neo4j)
- knowledge-mongodb

**Consumers**:
- knowledge-dashboard
- AI services (context retrieval)

---

### knowledge-dashboard
**Namespace**: `cortex-knowledge`
**Type**: LoadBalancer Service
**Exposed**: `10.88.145.208:80`

**Role**: Knowledge Visualization Dashboard
**Responsibilities**:
- Visualize knowledge graph
- Search interface
- Entity browser
- Relationship explorer
- Analytics and insights
- Export functionality

**Dependencies**:
- knowledge-graph-api

**Consumers**:
- Web browsers (users)

---

### improvement-detector
**Namespace**: `cortex-knowledge`
**Type**: ClusterIP Service
**Ports**: `8080`, `9092` (metrics)

**Role**: Improvement Opportunity Detection
**Responsibilities**:
- Analyze code patterns for anti-patterns
- Detect performance bottlenecks
- Identify security vulnerabilities
- Suggest architecture improvements
- Track technical debt
- Generate improvement proposals

**Dependencies**:
- knowledge-graph-api
- code analysis tools

**Consumers**:
- Development workflows
- Architecture reviews

---

### value-stream-optimizer
**Namespace**: `cortex-knowledge`
**Type**: Standalone
**Ports**: `8000`, `9093` (metrics)

**Role**: Value Stream Optimization
**Responsibilities**:
- Analyze CI/CD pipelines
- Identify bottlenecks in delivery
- Optimize resource allocation
- Reduce lead time
- Improve deployment frequency

**Dependencies**:
- CI/CD metrics
- knowledge-graph-api

**Consumers**:
- DevOps teams
- Pipeline optimization

---

### phoenix
**Namespace**: `cortex-knowledge`
**Type**: ClusterIP Service
**Ports**: `6006` (UI), `4317` (OTLP), `9090` (metrics)
**Exposed**: `observability.ry-ops.dev`

**Role**: LLM Observability Platform
**Responsibilities**:
- Trace LLM interactions
- Token usage tracking
- Latency monitoring
- Cost per request
- Quality metrics
- Prompt evaluation
- Model comparison

**Dependencies**:
- OpenTelemetry collectors

**Consumers**:
- All AI services (send traces)
- Developers (UI)

---

### outline
**Namespace**: `cortex-knowledge`
**Type**: ClusterIP Service
**Port**: `3000`

**Role**: Wiki & Documentation Platform
**Responsibilities**:
- Team documentation wiki
- Collaborative editing
- Version control
- Search functionality
- Access control
- API documentation

**Dependencies**:
- postgres-postgresql
- redis

**Consumers**:
- Team members (web UI)

---

### knowledge-mongodb
**Namespace**: `cortex-knowledge`
**Type**: StatefulSet (1/1)
**Port**: `27017`

**Role**: Document Storage
**Responsibilities**:
- Store raw documents
- Full-text indexing
- Document metadata
- Version history

**Dependencies**:
- Longhorn storage

**Consumers**:
- knowledge-extractor
- knowledge-graph-api

---

### knowledge-elasticsearch
**Namespace**: `cortex-knowledge`
**Type**: StatefulSet (0/1)
**Ports**: `9200`, `9300`
**Status**: Not running

**Role**: Full-Text Search Engine
**Responsibilities** (when running):
- Full-text search across all documents
- Fuzzy matching
- Faceted search
- Aggregations

**Status**: Needs investigation

---

### knowledge-graph (Neo4j)
**Namespace**: `cortex-knowledge`
**Type**: Headless Service
**Ports**: `7474` (HTTP), `7687` (Bolt)

**Role**: Graph Database
**Responsibilities**:
- Store entity relationships
- Cypher query execution
- Pathfinding algorithms
- Graph analytics
- Relationship inference

**Dependencies**:
- Longhorn storage

**Consumers**:
- knowledge-graph-api

---

## Development Tools

### code-generator
**Namespace**: `cortex-dev`
**Type**: ClusterIP Service

**Role**: AI-Powered Code Generation
**Responsibilities**:
- Generate code from natural language
- Scaffold projects and components
- Create boilerplate code
- Implement design patterns
- Generate tests
- Documentation generation

**Dependencies**:
- Anthropic API (Claude)
- redis-service (cache)

**Consumers**:
- cortex-queue-worker
- Direct API clients

---

### issue-parser
**Namespace**: `cortex-dev`
**Type**: ClusterIP Service

**Role**: GitHub Issue Analysis
**Responsibilities**:
- Parse GitHub issues
- Extract requirements
- Identify related issues
- Suggest solutions
- Generate implementation plans
- Track issue relationships

**Dependencies**:
- GitHub API
- knowledge-graph-api

**Consumers**:
- cortex-queue-worker
- CI/CD pipelines

---

### repo-context
**Namespace**: `cortex-dev`
**Type**: ClusterIP Service

**Role**: Repository Context Analysis
**Responsibilities**:
- Analyze codebase structure
- Extract dependencies
- Identify code patterns
- Generate context summaries
- Build symbol index

**Dependencies**:
- Git repositories
- knowledge-graph-api

**Consumers**:
- code-generator
- issue-parser

---

## Security & Compliance

### falco-falcosidekick
**Namespace**: `cortex-security`
**Type**: ClusterIP Service
**Ports**: `2801`, `2810`

**Role**: Runtime Security Alert Forwarding
**Responsibilities**:
- Receive Falco security alerts
- Forward to multiple destinations
- Alert enrichment
- Deduplication
- Priority assignment

**Dependencies**:
- Falco DaemonSet

**Consumers**:
- falco-falcosidekick-ui
- External SIEM systems

---

### falco-falcosidekick-ui
**Namespace**: `cortex-security`
**Type**: ClusterIP Service
**Port**: `2802`

**Role**: Security Alerts Dashboard
**Responsibilities**:
- Display security alerts
- Alert filtering and search
- Incident timeline
- Threat analysis
- Alert acknowledgment

**Dependencies**:
- falco-falcosidekick

**Consumers**:
- Security team (web UI)

---

### trivy-cluster-scan
**Namespace**: `cortex-security`
**Type**: CronJob (daily 2am)

**Role**: Vulnerability Scanning
**Responsibilities**:
- Scan all container images
- Check for CVEs
- Scan Kubernetes manifests
- Detect misconfigurations
- Scan secrets
- Generate security reports

**Dependencies**:
- Kubernetes API
- Trivy database

**Consumers**:
- Security reports
- Compliance audits

---

### csaf-runtime
**Namespace**: `cortex-csaf`
**Type**: Deployment (2 replicas with HPA)

**Role**: Security Advisory Processing
**Responsibilities**:
- Process CSAF security advisories
- Match advisories to installed software
- Calculate risk scores
- Generate remediation plans
- Track patching status

**Dependencies**:
- csaf-registry
- csaf-postgres

**Consumers**:
- Security dashboards
- Patching workflows

---

### csaf-registry
**Namespace**: `cortex-csaf`
**Type**: Deployment (2 replicas)

**Role**: Advisory Registry
**Responsibilities**:
- Store security advisories
- Index by product/version
- API for advisory retrieval
- Subscription management

**Dependencies**:
- csaf-postgres

**Consumers**:
- csaf-runtime
- csaf-correlator

---

### csaf-correlator
**Namespace**: `cortex-csaf`
**Type**: ClusterIP Service

**Role**: Advisory Correlation
**Responsibilities**:
- Correlate advisories with assets
- Identify affected systems
- Calculate aggregate risk
- Generate impact reports

**Dependencies**:
- csaf-registry
- Asset inventory

**Consumers**:
- csaf-runtime

---

### csaf-prompt-engine
**Namespace**: `cortex-csaf`
**Type**: ClusterIP Service

**Role**: AI-Powered Advisory Analysis
**Responsibilities**:
- Analyze advisory content with AI
- Extract key information
- Suggest remediation steps
- Generate executive summaries

**Dependencies**:
- csaf-registry
- Anthropic API

**Consumers**:
- csaf-runtime

---

## Monitoring & Observability

### cortex-metrics-api
**Namespace**: `cortex-metrics`
**Type**: LoadBalancer Service
**Exposed**: `10.88.145.209:8080`

**Role**: Custom Metrics API
**Responsibilities**:
- Expose custom metrics
- Aggregate metrics from services
- Metrics transformation
- Historical metrics storage

**Dependencies**:
- cortex-metrics-collector
- postgres

**Consumers**:
- Grafana dashboards
- Monitoring systems

---

### cortex-metrics-exporter
**Namespace**: `cortex-metrics`
**Type**: ClusterIP Service
**Port**: `9134`
**Status**: 0/1 Error ❌

**Role**: Prometheus Exporter
**Responsibilities** (when working):
- Export metrics in Prometheus format
- Service discovery
- Metric labeling

**Status**: Needs investigation

---

### network-fabric-monitor
**Namespace**: `cortex-ai-infra`
**Type**: DaemonSet (5/7 running)

**Role**: Network Performance Monitoring
**Responsibilities**:
- Monitor network latency
- Track packet loss
- Bandwidth utilization
- Connection tracking
- Network anomaly detection

**Dependencies**:
- None (node-level monitoring)

**Consumers**:
- Prometheus
- Network analytics

---

### auto-fix-daemon
**Namespace**: `cortex-system`
**Type**: Deployment

**Role**: Automatic Issue Remediation
**Responsibilities**:
- Detect common issues
- Apply known fixes automatically
- Restart failed services
- Clear disk space
- Resolve networking issues
- Log remediation actions

**Dependencies**:
- Kubernetes API

**Consumers**:
- Self-healing workflows

---

## Data & Persistence

### postgres-postgresql
**Namespace**: `cortex-system`
**Type**: StatefulSet (1/1)
**Port**: `5432`

**Role**: Primary Relational Database
**Responsibilities**:
- Store application data
- User accounts and sessions
- Task queue metadata
- Workflow state
- Configuration data
- Audit logs

**Backup**:
- Daily backups (CronJob 2am)
- Backup retention policy
- Point-in-time recovery

**Dependencies**:
- Longhorn storage

**Consumers**:
- cortex-orchestrator
- Most application services
- csaf-postgres
- langflow

**Critical**: Yes - primary data store

---

### redis-master
**Namespace**: `cortex-system`
**Type**: StatefulSet (1/1)
**Port**: `6379`

**Role**: Primary Cache & Queue
**Responsibilities**:
- Task queue (priority queues)
- Session cache
- Rate limiting counters
- Pub/sub messaging
- Distributed locks

**Queues**:
- `cortex:queue:critical`
- `cortex:queue:high`
- `cortex:queue:medium`
- `cortex:queue:low`

**Dependencies**:
- Persistent volume

**Consumers**:
- cortex-orchestrator
- cortex-queue-worker
- Most services (caching)

**Critical**: Yes - queue and cache

---

### redis-queue
**Namespace**: `cortex`
**Type**: Deployment
**Port**: `6379`

**Role**: Application Task Queue
**Responsibilities**:
- YouTube improvement pipeline queues
- Application-level task queue
- Sorted sets (by score/priority)

**Queues**:
- `improvements:raw`
- `improvements:categorized`
- `improvements:validated`
- `improvements:approved`
- `improvements:pending_review`
- `improvements:deployed`
- `improvements:verified`
- `improvements:failed`

**Dependencies**:
- Persistent volume

**Consumers**:
- youtube-ingestion
- school-coordinator
- implementation-workers
- health-monitor

**Critical**: Yes - improvement pipeline

---

## Infrastructure & Platform

### cortex-resource-manager
**Namespace**: `cortex-system`
**Type**: LoadBalancer Service
**Exposed**: `10.88.145.204:8080`
**Status**: 1/1 running (1 backup crashing)

**Role**: Resource Allocation & Monitoring
**Responsibilities**:
- Monitor cluster resources
- Optimize resource allocation
- Prevent resource exhaustion
- Namespace quota management
- Cost optimization recommendations

**Dependencies**:
- Kubernetes API
- Prometheus metrics

**Consumers**:
- Cluster operators
- Auto-scaling systems

---

### cortex-live
**Namespace**: `cortex-live`
**Type**: ClusterIP Service

**Role**: Real-Time Cluster Dashboard
**Responsibilities**:
- Real-time cluster visualization
- Resource utilization graphs
- Pod lifecycle events
- Service health status
- Interactive dashboard

**Dependencies**:
- Kubernetes API
- Prometheus

**Consumers**:
- Web browsers (operators)

---

### cortex-live-cli
**Namespace**: `cortex-system`
**Type**: DaemonSet (5/7 running)

**Role**: Node-Level Live Monitoring
**Responsibilities**:
- Real-time node metrics
- Process monitoring
- Log tailing
- Performance profiling

**Dependencies**:
- Node-level access

**Consumers**:
- cortex-live dashboard

---

## CI/CD & GitOps

### el-github-webhook-listener
**Namespace**: `cortex-cicd`
**Type**: ClusterIP Service
**Exposed**: `tekton-webhooks.cortex.local`

**Role**: GitHub Webhook Receiver
**Responsibilities**:
- Receive GitHub webhooks
- Validate webhook signatures
- Trigger Tekton pipelines
- Event filtering
- Error handling and retry

**Dependencies**:
- Tekton Pipelines

**Consumers**:
- GitHub (webhook sender)

---

### ArgoCD (implicit)
**Namespace**: `argocd`
**Role**: GitOps Continuous Deployment

**Responsibilities**:
- Poll cortex-gitops repository (every 3 min)
- Detect manifest changes
- Auto-sync to cluster
- Self-heal drift
- Prune deleted resources
- Rollback support
- Multi-cluster management

**Applications Managed**:
1. cortex-system (49 resources)
2. cortex-core (16 resources)
3. cortex-chat (17 resources)
4. cortex-school (8 resources)
5. cortex-dev (8 resources)
6. cortex-cicd (3 resources)
7. cortex-security (12 resources)
8. cortex-knowledge (15 resources)

**Total**: 120+ resources

**Dependencies**:
- GitHub (cortex-gitops)
- Kubernetes API

**Consumers**:
- All Cortex namespaces

**Critical**: Yes - GitOps automation

---

## Support & Specialized Services

### grafana-pdf-service
**Namespace**: `cortex-chat`
**Type**: ClusterIP Service
**Exposed**: `cortex-reports.ry-ops.dev`

**Role**: Dashboard PDF Export
**Responsibilities**:
- Render Grafana dashboards to PDF
- Schedule report generation
- Email report delivery
- Custom report templates

**Dependencies**:
- Grafana API

**Consumers**:
- Report scheduling system
- Manual report requests

---

### docker-registry
**Namespace**: `cortex-chat`
**Type**: ClusterIP Service
**Port**: `5000`

**Role**: Local Container Registry
**Responsibilities**:
- Store container images
- Image pull/push
- Garbage collection
- Image scanning integration

**Dependencies**:
- Persistent volume

**Consumers**:
- All K8s nodes (image pulls)
- CI/CD pipelines

**Critical**: Yes - image storage

---

## Lifecycle Management

### lifecycle-auditor
**Namespace**: `cortex-lifecycle`
**Type**: CronJob (every 6 hours)

**Role**: Service Lifecycle Auditing
**Responsibilities**:
- Audit service states
- Detect stale services
- Identify unused resources
- Generate lifecycle reports
- Recommend cleanup

**Dependencies**:
- Kubernetes API

**Consumers**:
- Lifecycle reports
- Cleanup workflows

---

**Status**: Comprehensive roles & responsibilities as of 2026-01-15
**Total Components**: 100+ services with defined roles
