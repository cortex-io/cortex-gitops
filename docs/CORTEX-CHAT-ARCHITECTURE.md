# Cortex Chat Architecture

**Document Purpose**: Understanding how chat integrates with the Cortex MoE (Mixture of Experts) system
**Created**: 2026-01-20
**Status**: Living Documentation

---

## Executive Summary

Cortex Chat is NOT a simple chatbot - it's a gateway into the Cortex Mixture of Experts system. Every chat message is analyzed for intent, routed to specialized expert backends, and the conversation history is stored with semantic vectors for future context retrieval.

**Key Insight**: Chat doesn't call Claude directly. It routes through the MoE architecture to leverage specialist knowledge.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER (via Browser)                       │
│                  Accesses via Tailscale/VLAN 145                │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│               cortex-chat-frontend (NodePort 32308)             │
│  Single-page JavaScript application                             │
│  - User authentication                                          │
│  - Message composition                                          │
│  - Conversation management                                      │
│  - Real-time message display                                    │
└───────────────────────────┬─────────────────────────────────────┘
                            │ POST /api/chat
                            │ GET /api/conversations/{id}
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              MoE Router (chat-router.py)                        │
│  Intelligent routing layer                                      │
│  - Intent classification (via Claude)                           │
│  - Expert selection                                             │
│  - Confidence scoring                                           │
│  - Telemetry capture                                            │
└───────────────┬────────────┬────────────┬──────────────────────┘
                │            │            │
        ┌───────┴──┐    ┌────┴────┐    ┌─┴──────────┐
        │ Qdrant   │    │ Redis   │    │ Experts    │
        │ (Memory) │    │(Metrics)│    │ (Backends) │
        └──────────┘    └─────────┘    └────┬───────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 cortex-orchestrator                             │
│  Expert backends that process requests:                         │
│  - general: General conversation and task routing               │
│  - infrastructure: Kubernetes, deployment, infra management     │
│  - security: Vulnerability analysis, compliance                 │
│  - automation: Workflow automation, n8n, langflow               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. Frontend (cortex-chat-frontend)

**File**: `apps/cortex-chat/frontend-html-configmap.yaml`
**Service**: NodePort 32308
**Technology**: Single-page JavaScript application

**Responsibilities**:
- User login/authentication
- Message input and display
- Conversation list management
- Session ID generation
- API communication to MoE Router

**API Calls**:
```javascript
POST /api/auth/login
GET /api/conversations
GET /api/conversations/{sessionId}
GET /api/conversations/{sessionId}/messages
POST /api/chat {sessionId, message}
```

**Key Design**:
- Sends `sessionId` (not `conversation_id`) in request body
- Expects response format: `{conversation: {messages: [...]}}`
- Auto-creates conversations on first message

---

### 2. MoE Router (chat-router.py)

**File**: `cortex-platform/services/moe-router/chat-router.py`
**Container**: `moe-router` pod
**Service**: ClusterIP `moe-router.cortex-chat.svc.cluster.local:8080`

**Responsibilities**:
1. **Intent Classification**: Uses Claude to analyze user message and determine which expert should handle it
2. **Expert Routing**: Forwards request to appropriate cortex-orchestrator endpoint
3. **Memory Storage**: Stores conversation in Qdrant with semantic vectors
4. **Telemetry**: Captures routing decisions, latency, success rate to Redis

**Configuration** (from config.yaml or env vars):
```yaml
experts:
  - name: general
    endpoint: http://cortex-orchestrator.cortex.svc.cluster.local:8000
    weight: 1.0
    specialization: "general conversation and task routing"

  - name: infrastructure
    endpoint: http://cortex-orchestrator.cortex.svc.cluster.local:8000
    weight: 2.0
    specialization: "kubernetes, deployment, infrastructure management"

  - name: security
    endpoint: http://cortex-orchestrator.cortex.svc.cluster.local:8000
    weight: 2.0
    specialization: "security scanning, vulnerability analysis, compliance"

  - name: automation
    endpoint: http://cortex-orchestrator.cortex.svc.cluster.local:8000
    weight: 1.5
    specialization: "workflow automation, n8n, langflow"
```

**Dependencies**:
- Anthropic API (for intent classification)
- Qdrant (for conversation memory)
- Redis (for telemetry)
- cortex-orchestrator (for expert processing)

**Flow**:
```
1. Receive POST /api/chat {sessionId, message}
2. Classify intent using Claude: "Which expert should handle this?"
3. Calculate confidence scores for each expert
4. Select best expert (highest confidence)
5. Route request to cortex-orchestrator expert endpoint
6. Store {message, response, metadata} in Qdrant
7. Capture telemetry (expert, latency, success) to Redis
8. Return {response, expert, confidence} to frontend
```

---

### 3. Qdrant (Vector Memory)

**Service**: `qdrant.cortex-chat.svc.cluster.local:6333` (NodePort 32333)
**Purpose**: Semantic conversation storage

**What's Stored**:
- User messages
- Assistant responses
- Conversation IDs
- Timestamps
- Metadata (expert used, intent classification)
- Vector embeddings for semantic search

**Why Vectors?**:
Enables future features like:
- "Show me past conversations about Kubernetes"
- Context-aware responses based on conversation history
- Similar question detection
- Conversation clustering

---

### 4. Redis (Telemetry)

**Service**: `redis.cortex-chat.svc.cluster.local:6379` (NodePort 32379)
**Purpose**: Real-time routing metrics

**Data Captured**:
```
moe:telemetry:routing_decisions → Sorted set of routing events
moe:telemetry:expert_usage → Hash of expert usage counts
```

**Metrics Tracked**:
- Which expert was selected
- Intent classification results
- Response latency
- Success/failure status
- Timestamp

**Use Cases**:
- Dashboard showing expert utilization
- Identifying routing patterns
- Detecting misrouted requests
- Performance analysis

---

### 5. cortex-orchestrator (Expert Backend)

**Service**: `cortex-orchestrator.cortex.svc.cluster.local:8000`
**Namespace**: `cortex`

**Role**:
The actual "brain" that processes chat requests. MoE Router determines which expert specialization to use, then calls cortex-orchestrator with that context.

**How It Works**:
- Receives POST /chat {message, conversation_id, intent}
- Processes based on intent.expert (general/infrastructure/security/automation)
- Uses domain-specific prompts and context
- Returns structured response

**Integration with Cortex**:
- Connected to coordinator-master
- Has access to MCP servers (GitHub, Proxmox, UniFi, etc.)
- Can execute tasks via Cortex task queue
- Knows about Cortex infrastructure and services

---

## Key Design Decisions

### Why Not Direct Claude API?

**Wrong Approach** (what simple-chat-api.py did):
```python
# BAD: Direct Claude call, no context
response = anthropic_client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=conversations[conversation_id]
)
```

**Problems**:
- No intent classification
- No expert routing
- No conversation memory (beyond in-memory dict)
- No telemetry
- No integration with Cortex infrastructure
- Generic responses without Cortex context

**Correct Approach** (what chat-router.py does):
```python
# GOOD: Intent classification → Expert routing → Memory storage
intent = classify_intent(message)  # Ask Claude: "Which expert?"
expert = select_expert(intent)     # Route to specialist
response = expert.execute(message) # Get expert response
store_in_qdrant(message, response) # Save for context
capture_telemetry(intent, expert)  # Track metrics
```

**Benefits**:
- Intelligent routing to appropriate expert
- Conversation context stored with vectors
- Telemetry for improving routing over time
- Integration with full Cortex MoE system
- Expert responses have Cortex infrastructure knowledge

---

## Network Access (Tailscale Bridge)

**Problem Solved**: Services need to be accessible from:
- Local VLAN 145 network (10.88.145.0/24)
- Remote devices via Tailscale VPN

**Solution**: NodePort services accessible via any node IP

### External Access Points

| Service | Type | NodePort | Access URL |
|---------|------|----------|------------|
| cortex-chat-frontend | NodePort | 32308 | http://10.88.145.194:32308 |
| moe-router | ClusterIP | - | (Internal only) |
| qdrant | NodePort | 32333 (HTTP), 32334 (gRPC) | http://10.88.145.194:32333 |
| redis | NodePort | 32379 | 10.88.145.194:32379 |

**Why NodePort?**:
- LoadBalancer type used MetalLB L2 mode (ARP-based)
- ARP doesn't cross L3 VPN boundaries
- Tailscale operates at L3 (IP routing)
- NodePort provides stable ports accessible via routable IPs

**Tailscale Role**:
- Bridges k3s cluster IPs (10.88.145.x) with VPN clients
- Routes traffic from remote devices to node IPs
- Provides secure encrypted tunnel
- No need to expose services to public internet

---

## Dependencies & Prerequisites

### For chat-router.py to work:

1. ✅ **Qdrant** - Running and accessible
   - Pod: `qdrant-76b7cdcf7-dwlhh` (Running)
   - Service: NodePort 32333/32334
   - Storage: PVC `qdrant-storage`

2. ⚠️ **Redis** - Deployment exists but scaled to 0
   - Deployment: `redis` (0/0 replicas)
   - Service: NodePort 32379
   - **Action Required**: Scale up to 1 replica

3. ⚠️ **cortex-orchestrator** - Pod in Unknown state
   - Pod: `cortex-orchestrator-6c4b769d6c-l6qzk` (Unknown status)
   - Service: ClusterIP 10.43.234.57:8000
   - **Action Required**: Restart/fix pod

4. ✅ **Anthropic API Key** - Configured in secret
   - Secret: `cortex-chat-secrets` in `cortex-chat` namespace
   - Key field: `anthropic-api-key`

### Current Status (as of 2026-01-20):

**Working**:
- ✅ Frontend accessible at http://10.88.145.194:32308
- ✅ simple-chat-api.py running (workaround)
- ✅ Messages sending and displaying
- ✅ Qdrant running

**Broken**:
- ❌ MoE Router not running chat-router.py (using simple-chat-api.py instead)
- ❌ Redis scaled to 0 (no telemetry)
- ❌ cortex-orchestrator pod in Unknown state
- ❌ No expert routing happening
- ❌ No conversation memory storage
- ❌ Generic responses without Cortex context

---

## How to Restore Full MoE Chat

### Step 1: Fix cortex-orchestrator

```bash
# Check current status
kubectl get pod -n cortex -l app=cortex-orchestrator

# If in Unknown state, delete and let it recreate
kubectl delete pod -n cortex -l app=cortex-orchestrator

# Verify it comes back healthy
kubectl get pod -n cortex -l app=cortex-orchestrator
kubectl logs -n cortex -l app=cortex-orchestrator --tail=50
```

### Step 2: Scale up Redis

```bash
# Check current deployment
kubectl get deployment redis -n cortex-chat

# Scale to 1 replica
kubectl scale deployment redis -n cortex-chat --replicas=1

# Verify pod starts
kubectl get pod -n cortex-chat -l app=redis
kubectl logs -n cortex-chat -l app=redis --tail=20
```

### Step 3: Build and deploy chat-router.py

```bash
# Option A: Use existing Dockerfile.chat
cd ~/Projects/cortex-platform/services/moe-router
docker build -f Dockerfile.chat -t 10.43.170.72:5000/moe-router:latest .
docker push 10.43.170.72:5000/moe-router:latest

# Option B: Use Kaniko build job (GitOps way)
# Update moe-router-deployment.yaml to use Dockerfile.chat
# Remove command override (let container run chat-router.py by default)
# Commit and push to trigger ArgoCD sync
```

### Step 4: Remove command override from deployment

```yaml
# Current (wrong):
containers:
- name: moe-router
  image: 10.43.170.72:5000/moe-router:latest
  command: ["python", "simple-chat-api.py"]  # ❌ Remove this

# Correct:
containers:
- name: moe-router
  image: 10.43.170.72:5000/moe-router:latest
  # No command override - runs chat-router.py from Dockerfile.chat
```

### Step 5: Update environment variables

Ensure moe-router deployment has:
```yaml
env:
- name: ANTHROPIC_API_KEY
  valueFrom:
    secretKeyRef:
      name: cortex-chat-secrets
      key: anthropic-api-key
- name: QDRANT_HOST
  value: "qdrant.cortex-chat.svc.cluster.local"
- name: QDRANT_PORT
  value: "6333"
- name: REDIS_HOST
  value: "redis.cortex-chat.svc.cluster.local"
- name: REDIS_PORT
  value: "6379"
- name: TELEMETRY_ENABLED
  value: "true"
```

### Step 6: Verify end-to-end flow

```bash
# Watch MoE router logs
kubectl logs -f -n cortex-chat -l app=moe-router

# Send test message via frontend
# Look for:
# - Intent classification call to Claude
# - Expert selection (general/infrastructure/security/automation)
# - Route to cortex-orchestrator
# - Qdrant storage
# - Redis telemetry capture

# Check Qdrant has conversation stored
curl http://10.88.145.194:32333/collections/chat_memory/points

# Check Redis has telemetry
kubectl exec -n cortex-chat -it redis-<pod> -- redis-cli
> KEYS moe:telemetry:*
> HGETALL moe:telemetry:expert_usage
```

---

## Troubleshooting

### "Messages not displaying"

**Symptom**: Frontend shows empty conversation after sending message
**Cause**: Response format mismatch

**Frontend expects**:
```json
{
  "conversation": {
    "id": "session-...",
    "messages": [
      {"role": "user", "content": "..."},
      {"role": "assistant", "content": "..."}
    ]
  }
}
```

**Fix**: Ensure GET /api/conversations/{id} returns nested format with `conversation` wrapper

### "Expert routing not working"

**Symptom**: All messages get generic responses
**Possible Causes**:
1. Still running simple-chat-api.py instead of chat-router.py
2. cortex-orchestrator down/unreachable
3. Intent classification failing (check Anthropic API key)

**Debug**:
```bash
# Check which script is running
kubectl exec -n cortex-chat moe-router-<pod> -- ps aux | grep python

# Check cortex-orchestrator connectivity
kubectl exec -n cortex-chat moe-router-<pod> -- \
  curl -v http://cortex-orchestrator.cortex.svc.cluster.local:8000/health

# Check intent classification
kubectl logs -n cortex-chat moe-router-<pod> | grep "Intent classification"
```

### "Qdrant not storing conversations"

**Symptom**: No conversation history in Qdrant
**Possible Causes**:
1. Qdrant connection failing
2. Collection not created
3. Vector generation errors

**Debug**:
```bash
# Check Qdrant collections
curl http://10.88.145.194:32333/collections

# Check moe-router can reach Qdrant
kubectl exec -n cortex-chat moe-router-<pod> -- \
  curl -v http://qdrant.cortex-chat.svc.cluster.local:6333

# Look for Qdrant errors in logs
kubectl logs -n cortex-chat moe-router-<pod> | grep -i qdrant
```

---

## Future Enhancements

### Context-Aware Responses

With conversation history in Qdrant:
```python
# Retrieve similar past conversations
similar = qdrant_client.search(
    collection_name="chat_memory",
    query_vector=current_message_vector,
    limit=5
)

# Include in expert context
expert_request = {
    "message": message,
    "conversation_id": conversation_id,
    "intent": intent,
    "context": [s.payload for s in similar]  # Past relevant conversations
}
```

### Learning Router

Track routing accuracy:
```python
# After task completion, ask user: "Was this helpful?"
if user_feedback == "yes":
    redis_client.hincrby(f"routing_success:{expert}", 1)
else:
    redis_client.hincrby(f"routing_failure:{expert}", 1)

# Adjust confidence scores based on feedback
```

### Multi-Expert Routing

For complex queries, route to multiple experts:
```python
if intent.confidence < 0.7:
    # Low confidence - consult multiple experts
    responses = await asyncio.gather(*[
        expert.execute(message)
        for expert in top_3_experts
    ])
    final_response = synthesize_responses(responses)
```

---

## Related Documentation

- **MoE Architecture**: `~/Projects/blog/src/content/posts/2025-10-08-cortex-what-is-mixture-of-experts.md`
- **System Status**: `~/Projects/cortex-gitops/docs/CORTEX-SYSTEM-STATUS.md`
- **Network Redesign Plan**: `~/.claude/plans/hazy-fluttering-hearth.md`
- **Cortex Platform Code**: `~/Projects/cortex-platform/services/moe-router/`
- **GitOps Manifests**: `~/Projects/cortex-gitops/apps/cortex-chat/`

---

**Last Updated**: 2026-01-20
**Maintained By**: Claude Code (Control Plane)
**Status**: ✅ Documentation Complete - Implementation Pending
