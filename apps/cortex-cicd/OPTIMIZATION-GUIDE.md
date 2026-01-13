# Tekton CI/CD Pipeline Optimization Guide

**Date**: 2026-01-12
**Version**: 1.0.0
**Namespace**: cortex-cicd

---

## Executive Summary

This document describes the optimizations applied to Cortex Tekton pipelines to reduce build times, improve caching, and optimize resource usage.

### Expected Improvements

| Metric | Before | After (Target) | Improvement |
|--------|--------|----------------|-------------|
| First build time | ~10-15 min | ~10-15 min | Baseline |
| Subsequent builds | ~10-15 min | ~3-5 min | **60-70% faster** |
| Layer rebuild | Every build | Cached | **90% reduction** |
| Dependency install | Every build | Cached | **80% reduction** |
| Test + Build time | Sequential | Parallel | **30-40% faster** |
| Storage efficiency | Ephemeral | Persistent | Better reuse |

---

## What Was Changed

### 1. Persistent Build Cache (20Gi)

**New Resource**: `build-cache-pvc.yaml`

- **Type**: PersistentVolumeClaim with ReadWriteMany access
- **Size**: 20Gi
- **Purpose**: Store Kaniko layer cache between builds
- **Impact**: Dramatically reduces image build time on subsequent builds

**How it works**:
- Kaniko caches intermediate Docker layers in `/cache`
- On subsequent builds, unchanged layers are reused
- Only modified layers are rebuilt
- Cache persists across pipeline runs

### 2. Persistent Dependency Cache (10Gi)

**New Resource**: `build-cache-pvc.yaml` (second PVC)

- **Type**: PersistentVolumeClaim with ReadWriteMany access
- **Size**: 10Gi
- **Purpose**: Cache npm packages, pip packages, go modules
- **Impact**: Eliminates repeated package downloads

**Cached directories**:
- `/cache/npm` - npm packages
- `/cache/pip` - Python packages
- `/cache/go/pkg/mod` - Go modules
- `/cache/go/build` - Go build cache

### 3. Optimized Kaniko Build Task

**New Task**: `task-kaniko-build-optimized.yaml`

**Key optimizations**:

```yaml
# Layer caching
- --cache=true
- --cache-dir=/cache
- --cache-ttl=168h  # 7 days
- --compressed-caching=true
- --cache-repo=10.43.170.72:5000/cache/[image]

# Performance
- --snapshot-mode=redo  # Faster than 'full'
- --use-new-run=true    # BuildKit-style RUN
```

**Resource increases**:
- CPU: 200m → 500m (request), 1000m → 2000m (limit)
- Memory: 512Mi → 1Gi (request), 2Gi → 4Gi (limit)

**Why**: More resources = faster builds, cache lookup, compression

### 4. Optimized Test Task with Dependency Caching

**New Task**: `task-run-tests-optimized.yaml`

**Key optimizations**:

```bash
# npm caching
export NPM_CONFIG_CACHE=/cache/npm
npm ci --prefer-offline --cache /cache/npm

# pip caching
export PIP_CACHE_DIR=/cache/pip
pip install --cache-dir /cache/pip -r requirements.txt

# go caching
export GOMODCACHE=/cache/go/pkg/mod
export GOCACHE=/cache/go/build
```

**Resource increases**:
- CPU: 100m → 200m (request), 500m → 1000m (limit)
- Memory: 256Mi → 512Mi (request), 1Gi → 2Gi (limit)

**Impact**:
- First run: Downloads packages to cache (~2-3 min)
- Subsequent runs: Uses cached packages (~10-30 sec)

### 5. Parallel Test and Build Execution

**New Pipeline**: `pipeline-test-build-deploy-optimized.yaml`

**Before** (Sequential):
```
fetch → test → build → scan → deploy
       (3m)   (10m)   (2m)    (1m)
Total: ~16 minutes
```

**After** (Parallel):
```
fetch → ┬→ test (3m) ──┐
        │              ├→ scan → deploy
        └→ build (3m) ─┘
Total: ~7 minutes (with cache)
```

**Key change**: Tests and build run simultaneously after fetch, security scan waits for both

### 6. Optimized Trigger Template

**New Template**: `triggertemplate-github-build-optimized.yaml`

**Changes**:
- Uses `build-push-pipeline-optimized` instead of `build-push-pipeline`
- Mounts persistent cache workspaces
- Increased ephemeral workspace: 1Gi → 2Gi (for larger repos)

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│           GitHub Webhook Event                   │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│      EventListener → TriggerTemplate            │
│   (github-build-template-optimized)             │
└────────────────┬────────────────────────────────┘
                 │
                 ▼ Creates PipelineRun
┌─────────────────────────────────────────────────┐
│         build-push-pipeline-optimized            │
│                                                  │
│  1. fetch-repository (git-clone)                │
│       ↓                                          │
│  2. build-and-push (kaniko-build-optimized)     │
│       - Uses /cache (build-cache PVC)           │
│       - Persistent layer cache                  │
│       - Higher CPU/RAM                          │
│       ↓                                          │
│  3. security-scan (trivy-scan)                  │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│    test-build-deploy-pipeline-optimized          │
│                                                  │
│  1. fetch-repository                            │
│       ↓                                          │
│  ┌────────────────┬──────────────────┐          │
│  │                │                  │          │
│  ▼                ▼                  │          │
│  2a. run-tests   2b. build-and-push │          │
│  (parallel)      (parallel)          │          │
│  - Uses /cache   - Uses /cache       │          │
│  (dependency)    (build)             │          │
│  └────────┬──────┴──────────────────┘          │
│           ▼                                      │
│  3. security-scan (waits for both)              │
│       ↓                                          │
│  4. deploy-with-helm (conditional)              │
└─────────────────────────────────────────────────┘
```

---

## How to Use Optimized Pipelines

### Option 1: Deploy All New Resources (Recommended)

ArgoCD will auto-sync the new manifests. New resources will be created alongside existing ones.

**Result**:
- Old pipelines continue to work
- New optimized pipelines available for testing
- Zero downtime migration

### Option 2: Update Existing TriggerTemplate

Edit `triggertemplate-github-build.yaml` to use `build-push-pipeline-optimized`:

```yaml
spec:
  resourcetemplates:
    - spec:
        pipelineRef:
          name: build-push-pipeline-optimized  # Changed
```

### Option 3: Manual Pipeline Run

Test the optimized pipeline manually:

```bash
kubectl create -f - <<EOF
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  generateName: test-optimized-
  namespace: cortex-cicd
spec:
  pipelineRef:
    name: build-push-pipeline-optimized
  params:
    - name: git-url
      value: https://github.com/your-org/your-repo
    - name: git-revision
      value: main
    - name: image-name
      value: test-app
    - name: image-tag
      value: test-123
  workspaces:
    - name: shared-workspace
      volumeClaimTemplate:
        spec:
          accessModes: [ReadWriteOnce]
          resources:
            requests:
              storage: 2Gi
    - name: build-cache
      persistentVolumeClaim:
        claimName: build-cache
    - name: dependency-cache
      persistentVolumeClaim:
        claimName: dependency-cache
    - name: docker-credentials
      secret:
        secretName: registry-credentials
EOF
```

---

## Measuring Performance

### Before Optimization

```bash
# Get baseline build time
kubectl get pipelinerun <old-run-name> -n cortex-cicd -o json | \
  jq -r '.status.completionTime as $end | .status.startTime as $start |
  (($end | fromdateiso8601) - ($start | fromdateiso8601)) | "Build time: \(.) seconds"'
```

### After Optimization

```bash
# Compare first run (cold cache)
kubectl get pipelinerun <new-run-1> -n cortex-cicd -o json | \
  jq -r '.status.completionTime as $end | .status.startTime as $start |
  (($end | fromdateiso8601) - ($start | fromdateiso8601)) | "Cold cache: \(.) seconds"'

# Compare second run (warm cache)
kubectl get pipelinerun <new-run-2> -n cortex-cicd -o json | \
  jq -r '.status.completionTime as $end | .status.startTime as $start |
  (($end | fromdateiso8601) - ($start | fromdateiso8601)) | "Warm cache: \(.) seconds"'
```

### Check Cache Utilization

```bash
# SSH into a build pod and check cache sizes
kubectl exec -it <kaniko-pod> -n cortex-cicd -- du -sh /cache

# Expected output:
# 1.2G    /cache  (after first build)
# 3.5G    /cache  (after multiple builds)
```

---

## Cache Maintenance

### Monitor Cache Growth

```bash
# Check PVC usage
kubectl get pvc -n cortex-cicd

# Describe PVC to see capacity
kubectl describe pvc build-cache -n cortex-cicd
kubectl describe pvc dependency-cache -n cortex-cicd
```

### Clear Cache (if needed)

```bash
# Delete and recreate PVC (nuclear option)
kubectl delete pvc build-cache -n cortex-cicd
kubectl delete pvc dependency-cache -n cortex-cicd

# ArgoCD will recreate from manifests
```

### Partial Cache Clear

```bash
# Create a cleanup job
kubectl create -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: clear-build-cache
  namespace: cortex-cicd
spec:
  template:
    spec:
      containers:
      - name: cleanup
        image: alpine:latest
        command: ["/bin/sh", "-c"]
        args:
          - |
            echo "Clearing build cache older than 7 days..."
            find /cache -type f -mtime +7 -delete
            echo "Done"
        volumeMounts:
        - name: cache
          mountPath: /cache
      volumes:
      - name: cache
        persistentVolumeClaim:
          claimName: build-cache
      restartPolicy: Never
EOF
```

---

## Best Practices for New Pipelines

### 1. Always Use Caching

```yaml
workspaces:
  - name: build-cache
    persistentVolumeClaim:
      claimName: build-cache
  - name: dependency-cache
    persistentVolumeClaim:
      claimName: dependency-cache
```

### 2. Optimize Dockerfiles for Caching

**Bad** (cache busted on every code change):
```dockerfile
COPY . /app
RUN npm install
```

**Good** (dependencies cached separately):
```dockerfile
COPY package*.json /app/
RUN npm ci --prefer-offline
COPY . /app
```

### 3. Use Multi-Stage Builds

```dockerfile
# Build stage (cached)
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --prefer-offline
COPY . .
RUN npm run build

# Runtime stage (smaller final image)
FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
CMD ["node", "dist/index.js"]
```

### 4. Right-Size Resources

**Small projects** (< 100MB):
- CPU: 200m request, 1000m limit
- Memory: 512Mi request, 2Gi limit

**Medium projects** (100MB - 1GB):
- CPU: 500m request, 2000m limit
- Memory: 1Gi request, 4Gi limit

**Large projects** (> 1GB):
- CPU: 1000m request, 4000m limit
- Memory: 2Gi request, 8Gi limit

### 5. Parallel Execution Patterns

**Safe to parallelize**:
- Linting + Tests
- Unit tests + Integration tests
- Building multiple services

**Not safe to parallelize**:
- Tests → Build (tests validate code before building)
- Build → Deploy (need artifact before deploying)

---

## Troubleshooting

### Cache Not Working

**Symptoms**: Build times not improving on subsequent runs

**Checks**:
```bash
# 1. Verify PVC exists and is bound
kubectl get pvc -n cortex-cicd

# 2. Check PipelineRun uses cache workspace
kubectl get pipelinerun <run-name> -n cortex-cicd -o yaml | grep -A5 workspaces

# 3. Check pod mounts
kubectl describe pod <build-pod> -n cortex-cicd | grep -A10 Mounts
```

**Solution**: Ensure PipelineRun includes cache workspaces

### Out of Memory During Build

**Symptoms**: Pod killed with OOMKilled status

**Checks**:
```bash
kubectl describe pod <build-pod> -n cortex-cicd | grep -i oom
```

**Solutions**:
1. Increase memory limits in task
2. Reduce concurrency in build tool (npm/go)
3. Use multi-stage builds to reduce memory footprint

### Cache Storage Full

**Symptoms**: PVC at 100% capacity

**Checks**:
```bash
kubectl describe pvc build-cache -n cortex-cicd
```

**Solutions**:
1. Increase PVC size (edit manifest, ArgoCD syncs)
2. Run cache cleanup job (see Cache Maintenance)
3. Reduce --cache-ttl in kaniko task

---

## Performance Benchmarks

### Expected Build Times (5 builds on same repo/branch)

| Build # | Cache State | Expected Time | Notes |
|---------|-------------|---------------|-------|
| 1 | Cold | 10-15 min | Downloads everything |
| 2 | Warm | 3-5 min | Uses layer + dep cache |
| 3 | Warm | 2-4 min | Cache fully populated |
| 4 | Warm | 2-4 min | Consistent performance |
| 5 | Warm | 2-4 min | Cached builds stable |

### Breakdown by Task

| Task | Before | After (Cold) | After (Warm) | Savings |
|------|--------|--------------|--------------|---------|
| git-clone | 30s | 30s | 30s | 0% |
| install-deps | 2-3 min | 2-3 min | 10-30s | 80% |
| run-tests | 1-2 min | 1-2 min | 1-2 min | 0% |
| build-and-push | 8-12 min | 8-12 min | 1-2 min | 85% |
| trivy-scan | 1-2 min | 1-2 min | 1-2 min | 0% |
| **Total** | **13-20 min** | **13-20 min** | **3-6 min** | **65-70%** |

---

## Migration Checklist

- [ ] Verify ArgoCD synced new PVCs (build-cache, dependency-cache)
- [ ] Confirm PVCs are Bound (not Pending)
- [ ] Test optimized pipeline with manual PipelineRun
- [ ] Compare build times (before vs. after)
- [ ] Verify cache directories populate (/cache)
- [ ] Update TriggerTemplate to use optimized pipeline
- [ ] Monitor first 5 builds for performance
- [ ] Document actual build time improvements
- [ ] Archive old pipeline manifests (optional)
- [ ] Update team documentation with new pipeline names

---

## File Summary

| File | Purpose |
|------|---------|
| `build-cache-pvc.yaml` | Persistent storage for Kaniko layers (20Gi) |
| `build-cache-pvc.yaml` | Persistent storage for dependencies (10Gi) |
| `task-kaniko-build-optimized.yaml` | Optimized build task with caching |
| `task-run-tests-optimized.yaml` | Optimized test task with dep caching |
| `pipeline-build-push-optimized.yaml` | Optimized build pipeline |
| `pipeline-test-build-deploy-optimized.yaml` | Optimized full CI/CD with parallel execution |
| `triggertemplate-github-build-optimized.yaml` | Webhook trigger for optimized pipeline |

---

## Support

For issues or questions:
1. Check ArgoCD application status: `kubectl get application cortex-cicd -n argocd`
2. View pipeline runs: `kubectl get pipelineruns -n cortex-cicd`
3. Check pod logs: `kubectl logs -n cortex-cicd <pod-name>`
4. Review this guide for troubleshooting steps

---

**Last Updated**: 2026-01-12
**Maintained By**: Cortex Platform Team
**GitOps Repo**: cortex-gitops/apps/cortex-cicd
