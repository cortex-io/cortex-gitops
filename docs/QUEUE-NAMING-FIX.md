# YouTube Ingestion Queue Naming Fix

**Date**: 2026-01-18
**Status**: IN PROGRESS

## Problem

youtube-ingestion pushes improvements to `youtube:improvements` but school-coordinator expects `improvements:raw`.

## Current State

- **Queue**: `youtube:improvements` (25 improvements waiting)
- **Expected**: `improvements:raw` → `improvements:categorized` → `improvements:validated` → `improvements:approved` → `improvements:implemented` → `improvements:deployed` → `improvements:verified`

## Solution

### Phase 1: Quick Fix (Manual Redis Rename) ✅ DOING NOW

Rename existing queue to unblock pipeline immediately:

```bash
kubectl exec -n cortex redis-queue-7d9d7f4c7b-t5nfq -- redis-cli RENAME youtube:improvements improvements:raw
```

### Phase 2: Proper Fix (Update Code)

1. Add environment variable to youtube-ingestion deployment:
   ```yaml
   - name: IMPROVEMENTS_QUEUE
     value: improvements:raw
   ```

2. Update ingestion-service.js ConfigMap to use env var:
   ```javascript
   const queueName = process.env.IMPROVEMENTS_QUEUE || 'improvements:raw';
   await this.redis.lpush(queueName, JSON.stringify(analysis));
   ```

3. Commit to gitops and let ArgoCD deploy

## Queue Flow

```
youtube-ingestion
    ↓ (pushes to)
improvements:raw
    ↓ (school-coordinator pops)
moe-router
    ↓ (pushes to)
improvements:categorized
    ↓ (school-coordinator pops)
rag-validator
    ↓ (pushes to)
improvements:validated
    ↓ (school-coordinator auto-approval)
improvements:approved
    ↓ (implementation-workers pop)
improvements:implemented
    ↓ (after git commit)
improvements:deployed
    ↓ (health-monitor validates)
improvements:verified ✅
```

## References

- Deployment: `apps/cortex/youtube-ingestion-deployment.yaml`
- ConfigMap: `youtube-ingestion-fixes` (namespace: cortex)
- School Coordinator: `apps/cortex-school/coordinator-deployment.yaml`
