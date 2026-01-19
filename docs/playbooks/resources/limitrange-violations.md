# Playbook: LimitRange Violations
**Category**: Resources
**Last Updated**: 2026-01-18
**Severity**: Medium

---

## Symptoms

- Pod creation fails with "forbidden" error
- Error message: "memory/cpu max limit to request ratio per Container is X, but provided ratio is Y"
- Deployment shows desired replicas but no pods created
- Events show resource quota or limit violations

## Quick Diagnosis

```bash
# Check deployment status
kubectl get deployment <name> -n <namespace>
# Shows: READY 0/1, AVAILABLE 0

# Check replica set events
kubectl describe rs -n <namespace> | grep -A 5 "Error creating"
# Look for: "forbidden: [memory/cpu] max limit to request ratio"

# Check namespace LimitRange
kubectl get limitrange -n <namespace>
kubectl describe limitrange -n <namespace>
```

## Investigation Steps

### 1. Check LimitRange Policy

**Command**:
```bash
kubectl get limitrange -n <namespace> -o yaml
```

**What to Look For**:
```yaml
spec:
  limits:
  - maxLimitRequestRatio:
      cpu: "4"      # Max ratio 4:1
      memory: "2"   # Max ratio 2:1
    type: Container
```

### 2. Check Pod Resource Specification

**File to Check**: `apps/<namespace>/<deployment>.yaml`

**Command**:
```bash
kubectl get deployment <name> -n <namespace> -o jsonpath='{.spec.template.spec.containers[*].resources}'
```

**Calculate Ratios**:
- CPU ratio = limits.cpu / requests.cpu
- Memory ratio = limits.memory / requests.memory
- Both must be ≤ LimitRange maxLimitRequestRatio

### 3. Common Violations

**Example Violation** (4:1 memory, should be 2:1):
```yaml
resources:
  requests:
    memory: 256Mi
  limits:
    memory: 1Gi    # Ratio: 1024/256 = 4:1 ✗ FAILS
```

**Fixed Version**:
```yaml
resources:
  requests:
    memory: 512Mi  # Increased request
  limits:
    memory: 1Gi    # Ratio: 1024/512 = 2:1 ✓ PASSES
```

## Common Root Causes

### Cause A: Resource Ratios Exceed LimitRange Policy

**Solution**:
1. Edit deployment manifest: `apps/<namespace>/<deployment>.yaml`

2. Adjust resources to comply with ratios:
   ```yaml
   resources:
     requests:
       cpu: 250m      # Changed from 100m
       memory: 512Mi  # Changed from 256Mi
     limits:
       cpu: 1000m     # Ratio: 1000/250 = 4:1 ✓
       memory: 1Gi    # Ratio: 1024/512 = 2:1 ✓
   ```

3. Commit and push:
   ```bash
   git add apps/<namespace>/<deployment>.yaml
   git commit -m "Fix resource limits to comply with LimitRange (CPU 4:1, Memory 2:1)"
   git push origin main
   ```

**Verification**:
```bash
kubectl get pods -n <namespace>
# Expected: Pod created and running
```

### Cause B: Default Resource Limits Too Restrictive

**Solution** (if you control namespace):
1. Modify LimitRange: `apps/<namespace>/<namespace>-limits.yaml`
2. Increase maxLimitRequestRatio values
3. Apply changes via GitOps

**Not Recommended**: Loosening limits reduces resource protection

## Prevention

- **Know your namespace limits**: Check LimitRange before creating deployments
- **Use compliant defaults**: Start with 250m/1000m CPU, 512Mi/1Gi memory
- **Calculate ratios**: requests × 4 ≤ limits (CPU), requests × 2 ≤ limits (memory)
- **Test in dev namespace first**: Catch violations before production

## Related Playbooks

- [OOM Killed](./oom-killed.md) - Insufficient memory limits
- [Pod Scheduling Issues](./pod-scheduling.md) - Resource quota violations

## Real Examples

### Example 1: Qdrant Deployment LimitRange Violation
- **Date**: 2026-01-18 (from session summary)
- **Issue**: Qdrant pod creation forbidden
- **Error**: `memory max limit to request ratio per Container is 2, but provided ratio is 4.000000, cpu max limit to request ratio per Container is 4, but provided ratio is 10.000000`
- **Original Config**:
  ```yaml
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 1000m    # Ratio: 10:1
    memory: 1Gi   # Ratio: 4:1
  ```
- **Fixed Config**:
  ```yaml
  requests:
    cpu: 250m     # Changed
    memory: 512Mi # Changed
  limits:
    cpu: 1000m    # Ratio: 4:1 ✓
    memory: 1Gi   # Ratio: 2:1 ✓
  ```
- **Resolution**: Updated resource requests to comply with ratios
- **Result**: Qdrant pod started successfully (1/1 Ready)

---

## Usage Notes

**When to use this playbook**:
- Pod creation fails with "forbidden" error
- Resource ratio violations in events
- Deployment stuck at 0 replicas

**When NOT to use this playbook**:
- Pod is pending (insufficient cluster resources) → Different issue
- Pod is running but slow → Performance tuning needed
