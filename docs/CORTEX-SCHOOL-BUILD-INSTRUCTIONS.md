# Cortex Online School - Build Instructions

**Date**: 2026-01-14
**Status**: Code complete, ready to build images

---

## What's Been Completed

### ✅ Service Code Written (17 files, 1,658 lines)

All 5 microservices have been implemented and committed to `cortex-platform`:

1. **Coordinator** (`services/coordinator/`)
   - Main orchestration service
   - Manages Redis pipeline stages
   - Auto-approval logic
   - 256 lines Python

2. **MoE Router** (`services/moe-router/`)
   - Routes to 6 specialized expert agents
   - Anthropic API integration
   - LLM-D coordination ready
   - 195 lines Python

3. **RAG Validator** (`services/rag-validator/`)
   - Qdrant vector search
   - OpenAI embeddings
   - Conflict detection
   - 243 lines Python

4. **Implementation Worker** (`services/implementation-worker/`)
   - Manifest generation
   - Git commit automation
   - GitHub integration
   - 255 lines Python

5. **Health Monitor** (`services/health-monitor/`)
   - Kubernetes API integration
   - Prometheus metrics checking
   - Automatic rollback
   - 309 lines Python

### ✅ Infrastructure Deployed

- **Namespace**: cortex-school ✅
- **Manifests**: 8 YAML files in cortex-gitops ✅
- **ArgoCD Application**: Created and syncing ✅
- **Pods**: 9 pods scheduled (waiting for images) ⏳

### ✅ Documentation Complete

- **Architecture**: cortex-docs/vault/architecture/cortex-online-school.md (1,350 lines)
- **Service README**: cortex-platform/services/README-CORTEX-SCHOOL.md (346 lines)
- **Build Script**: cortex-platform/services/cortex-school-build.sh

### ✅ Git Commits

- **cortex-docs**: `947edbf` (architecture documentation)
- **cortex-gitops**: `a5f7c51` (Kubernetes manifests)
- **cortex-platform**: `a8425f8` (service implementations)

---

## Next Step: Build Docker Images

The service code is complete and ready to build. You need to run the build script on a machine that has:
- Docker installed
- Access to push to `10.43.170.72:5000` registry

### Option 1: Build on K3s Node (Recommended)

SSH to one of your K3s nodes that has Docker/containerd access:

```bash
# Clone the repository
cd ~
git clone https://github.com/ry-ops/cortex-platform.git
cd cortex-platform/services

# Run the build script
./cortex-school-build.sh
```

The script will:
1. Build all 5 Docker images
2. Tag for local registry `10.43.170.72:5000`
3. Push to registry
4. Display success confirmation

### Option 2: Build Manually (If Script Fails)

```bash
cd ~/cortex-platform/services

# Build coordinator
cd coordinator
docker build -t cortex-coordinator:latest .
docker tag cortex-coordinator:latest 10.43.170.72:5000/cortex-coordinator:latest
docker push 10.43.170.72:5000/cortex-coordinator:latest
cd ..

# Build moe-router
cd moe-router
docker build -t cortex-moe-router:latest .
docker tag cortex-moe-router:latest 10.43.170.72:5000/cortex-moe-router:latest
docker push 10.43.170.72:5000/cortex-moe-router:latest
cd ..

# Build rag-validator
cd rag-validator
docker build -t cortex-rag-validator:latest .
docker tag cortex-rag-validator:latest 10.43.170.72:5000/cortex-rag-validator:latest
docker push 10.43.170.72:5000/cortex-rag-validator:latest
cd ..

# Build implementation-worker
cd implementation-worker
docker build -t cortex-implementation-worker:latest .
docker tag cortex-implementation-worker:latest 10.43.170.72:5000/cortex-implementation-worker:latest
docker push 10.43.170.72:5000/cortex-implementation-worker:latest
cd ..

# Build health-monitor
cd health-monitor
docker build -t cortex-health-monitor:latest .
docker tag cortex-health-monitor:latest 10.43.170.72:5000/cortex-health-monitor:latest
docker push 10.43.170.72:5000/cortex-health-monitor:latest
cd ..
```

### Option 3: Use Buildah/Podman (If Docker Not Available)

Replace `docker` with `podman` or `buildah` in the commands above.

---

## After Building Images

### 1. Create Required Secrets

The services need API keys to function:

```bash
# Anthropic API key (for MoE expert routing)
kubectl create secret generic anthropic-api-key \
  -n cortex-school \
  --from-literal=key=YOUR_ANTHROPIC_API_KEY

# OpenAI API key (for RAG embeddings)
kubectl create secret generic openai-api-key \
  -n cortex-school \
  --from-literal=key=YOUR_OPENAI_API_KEY

# GitHub token (for Git commits and rollbacks)
kubectl create secret generic github-token \
  -n cortex-school \
  --from-literal=token=YOUR_GITHUB_TOKEN
```

### 2. Restart Pods

Once images are in the registry, delete the pending pods so ArgoCD recreates them:

```bash
kubectl delete pods -n cortex-school --all
```

ArgoCD will automatically recreate the pods and pull the new images.

### 3. Verify Deployment

```bash
# Check pod status
kubectl get pods -n cortex-school

# Should see all 9 pods Running:
# NAME                                     READY   STATUS
# school-coordinator-xxx                   1/1     Running
# moe-router-xxx                           1/1     Running
# rag-validator-xxx (x2)                   1/1     Running
# implementation-workers-xxx (x3)          1/1     Running
# health-monitor-xxx                       1/1     Running
# qdrant-0                                 1/1     Running

# Check coordinator logs
kubectl logs -n cortex-school -l app=school-coordinator --tail=50

# Check MoE router logs
kubectl logs -n cortex-school -l app=moe-router --tail=50

# Test coordinator API
kubectl port-forward -n cortex-school svc/school-coordinator 8080:8080
curl http://localhost:8080/health
curl http://localhost:8080/status
```

---

## Testing the Pipeline

### 1. Check YouTube Ingestion

Verify the YouTube service is generating improvements:

```bash
kubectl port-forward -n cortex svc/youtube-ingestion 8080:8080
curl http://localhost:8080/improvements
```

You should see 25+ improvements with relevance scores.

### 2. Monitor Redis Queues

Check that improvements are flowing through the pipeline:

```bash
kubectl exec -n cortex deploy/school-coordinator -- sh -c "
echo 'ZCARD improvements:raw' | redis-cli -h redis.cortex.svc.cluster.local
echo 'ZCARD improvements:categorized' | redis-cli -h redis.cortex.svc.cluster.local
echo 'ZCARD improvements:validated' | redis-cli -h redis.cortex.svc.cluster.local
echo 'ZCARD improvements:approved' | redis-cli -h redis.cortex.svc.cluster.local
echo 'ZCARD improvements:deployed' | redis-cli -h redis.cortex.svc.cluster.local
echo 'ZCARD improvements:verified' | redis-cli -h redis.cortex.svc.cluster.local
"
```

### 3. Watch for Git Commits

The implementation workers will create commits in `cortex-gitops`:

```bash
cd ~/Projects/cortex-gitops
git pull origin main
git log --oneline | head -10

# Look for commits like:
# "Implement: Structure-aware chunking for RAG retrieval"
# "Implement: LLM-D distributed inference coordination"
```

### 4. Monitor ArgoCD

Watch ArgoCD sync the changes:

```bash
kubectl get application cortex-school -n argocd -w
```

---

## Troubleshooting

### Images still ErrImagePull after building

Check if images are in registry:

```bash
# On a node with registry access
curl http://10.43.170.72:5000/v2/_catalog

# Should show cortex-* images
```

### Pods CrashLoopBackOff

Check logs for errors:

```bash
kubectl logs -n cortex-school <pod-name>
kubectl describe pod -n cortex-school <pod-name>
```

Common issues:
- Missing API key secrets
- Redis connection failure
- Qdrant not ready

### No improvements flowing

1. Check YouTube ingestion is running:
   ```bash
   kubectl get pods -n cortex -l app=youtube-ingestion
   ```

2. Check coordinator is processing:
   ```bash
   kubectl logs -n cortex-school -l app=school-coordinator --tail=100
   ```

3. Manually add a test improvement to Redis:
   ```bash
   kubectl exec -n cortex deploy/redis -- redis-cli ZADD improvements:raw $(date +%s) '{"title":"Test","relevance":0.95,"category":"architecture"}'
   ```

### GitHub commits failing

Check GitHub token is valid:

```bash
kubectl get secret github-token -n cortex-school -o jsonpath='{.data.token}' | base64 -d
```

Test token has correct permissions:
- Repo: Full control
- Workflow: Update workflows

---

## Expected Behavior Once Running

### Fully Autonomous Pipeline

1. **YouTube service** ingests videos every hour
2. **Improvements** added to `improvements:raw` queue
3. **Coordinator** picks improvements and routes to MoE
4. **MoE router** evaluates with specialized experts
5. **RAG validator** checks for conflicts
6. **Auto-approval** approves if ≥90% relevance
7. **Implementation workers** generate manifests
8. **Git commits** pushed to cortex-gitops
9. **ArgoCD syncs** within 3 minutes
10. **Health monitor** watches for 5 minutes
11. **Auto-rollback** if failures detected

### Zero Human Intervention

The system should operate 100% autonomously:
- ✅ Learning from YouTube videos
- ✅ Evaluating relevance
- ✅ Routing to experts
- ✅ Validating against existing infrastructure
- ✅ Auto-approving safe improvements
- ✅ Generating manifests
- ✅ Committing to Git
- ✅ Deploying via ArgoCD
- ✅ Monitoring health
- ✅ Rolling back failures

**"The infrastructure that teaches itself."**

---

## Summary

### What You Have
- ✅ 5 microservices (1,658 lines of production code)
- ✅ Complete architecture (1,350 lines of documentation)
- ✅ Kubernetes manifests (8 files, 692 lines)
- ✅ All code committed to GitHub
- ✅ ArgoCD Application deployed
- ✅ Build script ready

### What You Need To Do
1. Run `cortex-platform/services/cortex-school-build.sh` on a machine with Docker
2. Create 3 secrets (Anthropic, OpenAI, GitHub tokens)
3. Restart pods in cortex-school namespace
4. Watch the autonomous learning begin

### Files Modified/Created Today

**cortex-platform**:
- Commit: `a8425f8`
- Files: 17 new (services/coordinator/, moe-router/, etc.)

**cortex-gitops**:
- Commit: `a5f7c51`
- Files: apps/cortex-school/* (8 manifests)

**cortex-docs**:
- Commit: `947edbf`
- Files: vault/architecture/cortex-online-school.md

---

**Status**: 🎯 Ready to build images
**Next**: SSH to K3s node and run `./cortex-school-build.sh`
