# Next Steps: Fix Longhorn Volume Issues

**Date**: 2026-01-15
**Priority**: HIGH - Blocking Qdrant deployment
**Issue**: Longhorn replica NodeID mismatch preventing volume attachment

---

## Root Cause Identified

Longhorn is experiencing replica synchronization failures:

```
ERROR: instance pvc-xxx-r-xxx NodeID k3s-worker01 is not the same as
       instance manager instance-manager-xxx NodeID k3s-worker04
```

**What this means**:
- Longhorn replicas are registered to k3s-worker01
- But their instance managers are on k3s-worker04
- This mismatch prevents volume attachment
- Affects multiple volumes, not just Qdrant

---

## Immediate Workaround Options

### Option 1: Use emptyDir (Fast, but data loss on restart)

**Pros**: Gets Qdrant running immediately
**Cons**: Data lost if pod restarts (acceptable for dev/testing)

**Implementation**:
```yaml
# In qdrant-statefulset.yaml, replace volumeClaimTemplates with:
spec:
  template:
    spec:
      volumes:
      - name: qdrant-storage
        emptyDir: {}
```

**Commands**:
```bash
cd ~/Projects/cortex-gitops
# Edit apps/cortex-school/qdrant-statefulset.yaml
# Replace volumeClaimTemplates section with emptyDir volume
git add apps/cortex-school/qdrant-statefulset.yaml
git commit -m "Temporary: Use emptyDir for Qdrant (Longhorn issue workaround)"
git push origin main
# ArgoCD will sync within 3 minutes
```

---

### Option 2: Fix Longhorn Cluster (Proper, takes time)

**Pros**: Fixes root cause, preserves data
**Cons**: Requires cluster maintenance, may need node restarts

#### Step 1: Check Longhorn Instance Managers

```bash
kubectl get pods -n longhorn-system -l longhorn.io/component=instance-manager -o wide
```

Look for instance managers with issues or on wrong nodes.

#### Step 2: Restart Longhorn Managers on Affected Nodes

```bash
# Restart manager on k3s-worker01
kubectl delete pod -n longhorn-system -l app=longhorn-manager --field-selector spec.nodeName=k3s-worker01

# Wait 30 seconds for restart
sleep 30

# Check if errors cleared
kubectl logs -n longhorn-system -l app=longhorn-manager --tail=50 | grep -i error
```

#### Step 3: Check Volume Status

```bash
kubectl get volumes -n longhorn-system | grep cortex-school
```

Should show "healthy" instead of "faulted".

#### Step 4: Delete and Recreate Qdrant Pod

```bash
kubectl delete pod -n cortex-school qdrant-0
# StatefulSet will recreate it
sleep 20
kubectl get pods -n cortex-school
```

---

### Option 3: Recreate Longhorn Replicas (Nuclear option)

**Warning**: Only if Option 2 fails. May cause data loss for other volumes.

```bash
# List all faulted volumes
kubectl get volumes -n longhorn-system | grep faulted

# For each faulted volume (example):
kubectl delete volume -n longhorn-system pvc-a86d886e-5726-452f-b0c1-f8f6b3fa5865

# Delete the PVC
kubectl delete pvc -n cortex-school qdrant-storage-qdrant-0

# StatefulSet will recreate both
```

---

## Recommended Approach

**For immediate testing**: Use Option 1 (emptyDir)
- Gets Cortex School 100% operational in 5 minutes
- Acceptable for development/testing
- Can migrate to persistent storage later

**For production**: Fix Option 2 (Longhorn cluster)
- Schedule maintenance window
- Restart Longhorn managers
- Verify all volumes healthy
- Test pod scheduling

---

## Commands to Run (Option 1 - Fast Path)

```bash
# 1. Edit qdrant StatefulSet to use emptyDir
cd ~/Projects/cortex-gitops
cat > /tmp/qdrant-patch.yaml <<'EOF'
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: qdrant
  namespace: cortex-school
spec:
  template:
    spec:
      volumes:
      - name: qdrant-storage
        emptyDir:
          sizeLimit: 20Gi
  volumeClaimTemplates: []
EOF

# 2. Apply the patch
kubectl patch statefulset qdrant -n cortex-school --patch-file /tmp/qdrant-patch.yaml

# 3. Delete existing pod to force recreation
kubectl delete pod -n cortex-school qdrant-0 --force --grace-period=0

# 4. Wait and verify
sleep 30
kubectl get pods -n cortex-school

# Expected: qdrant-0 Running 1/1
# Expected: rag-validator becomes healthy (can connect to Qdrant)
```

---

## Verification Steps

After Qdrant is running:

```bash
# 1. Check Qdrant health
kubectl exec -n cortex-school qdrant-0 -- curl -s http://localhost:6333/ | jq .

# 2. Check rag-validator can connect
kubectl logs -n cortex-school rag-validator-76559b65d5-7gx66 --tail=20

# Should see: "Successfully connected to Qdrant"
# Should see: "Collection cortex-docs created"

# 3. Test full pipeline health
kubectl get pods -n cortex-school

# Expected all 6/6 Running:
# - school-coordinator: 1/1 Running
# - health-monitor: 1/1 Running
# - moe-router: 1/1 Running
# - rag-validator: 1/1 Running
# - implementation-workers: 1/1 Running
# - qdrant: 1/1 Running
```

---

## Long-term Fix (After emptyDir workaround)

Once Cortex School is operational with emptyDir:

1. **Investigate Longhorn root cause**:
   - Check node taints and labels
   - Review Longhorn instance manager scheduling
   - Verify disk health on all nodes

2. **Fix Longhorn cluster**:
   - Restart Longhorn managers systematically
   - Reconcile replica placement
   - Test volume creation/attachment

3. **Migrate Qdrant to persistent storage**:
   - Export Qdrant collections
   - Switch back to volumeClaimTemplates
   - Import collections to new persistent volume

---

## Why Longhorn is Failing

**NodeID Mismatch** indicates:
1. Instance manager pods were rescheduled to different nodes
2. Replicas still reference old NodeIDs
3. Longhorn controller can't reconcile the mismatch
4. Volumes go to "faulted" state

**Common causes**:
- Node drain/eviction moved instance managers
- Longhorn upgrade/restart without proper reconciliation
- Network partition causing split-brain
- Node failure and recovery

**Detection**:
```bash
# Check instance manager distribution
kubectl get pods -n longhorn-system -l longhorn.io/component=instance-manager \
  -o custom-columns=NAME:.metadata.name,NODE:.spec.nodeName,STATUS:.status.phase

# Check if any are on unexpected nodes
```

---

## Success Criteria

- [ ] Qdrant pod status: 1/1 Running
- [ ] Qdrant health endpoint responding (port 6333)
- [ ] rag-validator health checks passing (200 OK)
- [ ] No "Connection refused" errors in rag-validator logs
- [ ] All 6 cortex-school pods Running
- [ ] End-to-end pipeline functional

---

## Timeline Estimate

**Option 1 (emptyDir)**: 5-10 minutes
- Edit manifest: 2 min
- Git commit/push: 1 min
- Pod recreation: 2-5 min
- Verification: 2 min

**Option 2 (Fix Longhorn)**: 30-60 minutes
- Investigation: 10 min
- Manager restarts: 15 min
- Volume reconciliation: 10-20 min
- Testing: 10-15 min

---

## Risk Assessment

**Option 1 (emptyDir)**:
- Risk: LOW - Isolated to Qdrant pod only
- Impact: Data loss on pod restart (acceptable for vector DB)
- Rollback: Easy - revert to volumeClaimTemplates

**Option 2 (Fix Longhorn)**:
- Risk: MEDIUM - Cluster-wide storage system
- Impact: Potential downtime for workloads using Longhorn
- Rollback: Restart managers back to previous state

---

## Monitoring During Fix

Watch these metrics:
```bash
# Pod status
watch -n 5 'kubectl get pods -n cortex-school'

# Longhorn volumes
watch -n 5 'kubectl get volumes -n longhorn-system | grep cortex'

# Qdrant logs (once running)
kubectl logs -n cortex-school qdrant-0 -f

# rag-validator logs
kubectl logs -n cortex-school -l app=rag-validator -f --max-log-requests 2
```

---

## Next Session Checklist

- [ ] Review this document
- [ ] Decide: emptyDir (fast) vs Fix Longhorn (proper)
- [ ] Execute chosen option
- [ ] Verify 6/6 cortex-school pods running
- [ ] Test YouTube → ArgoCD pipeline end-to-end
- [ ] Fix remaining ArgoCD drift (8 applications)
- [ ] Re-enable cortex-metrics services
- [ ] Document production-ready Longhorn configuration

---

**Current Status**: 4/6 cortex-school pods running (67%)
**Blocker**: Longhorn replica NodeID mismatch
**ETA to 100%**: 10 minutes (emptyDir) OR 60 minutes (proper fix)
**Recommendation**: Use emptyDir for immediate progress, fix Longhorn in parallel
