# Playbook: [Issue Name]
**Category**: [Pod Debugging / Network / Resources / GitOps]
**Last Updated**: YYYY-MM-DD
**Severity**: [Low / Medium / High / Critical]

---

## Symptoms

- Observable symptom 1
- Pod status indicators (CrashLoopBackOff, ImagePullBackOff, etc.)
- Error messages in logs or events
- User-facing impact

## Quick Diagnosis

```bash
# Commands to run for initial assessment
kubectl get pods -n <namespace>
kubectl describe pod <pod-name> -n <namespace> | grep -A 10 "Events:"

# Expected output:
# [Example of what you should see]
```

## Investigation Steps

### 1. [First Check - e.g., Check Pod Events]

**File to Check**: `apps/<namespace>/<resource>.yaml:line`
**Command**:
```bash
kubectl describe pod <pod-name> -n <namespace>
```
**What to Look For**:
- Expected state vs actual state
- Specific error messages
- Resource configurations

### 2. [Second Check - e.g., Verify Configuration]

**File to Check**: `apps/<namespace>/<resource>.yaml:line`
**Command**:
```bash
kubectl get <resource> -n <namespace> -o yaml
```
**What to Look For**:
- Configuration mismatches
- Missing required fields
- Incorrect values

### 3. [Third Check - e.g., Check Related Resources]

**Command**:
```bash
kubectl get svc,deploy,cm -n <namespace>
```
**What to Look For**:
- Related resource status
- Dependencies
- Network connectivity

## Common Root Causes

### Cause A: [Description]

**Indicators**:
- Specific log messages
- Event patterns
- Configuration states

**Solution**:
1. Step-by-step fix procedure
2. Files to modify: `path/to/file.yaml:line`
3. Commands to run

**Verification**:
```bash
# Commands to confirm fix worked
kubectl get pods -n <namespace>
# Expected: Pod status = Running
```

### Cause B: [Description]

**Indicators**:
- Different symptoms
- Alternative patterns

**Solution**:
1. Alternative fix procedure
2. Configuration changes needed

**Verification**:
- How to confirm resolution

## Prevention

- Configuration best practices to avoid this issue
- Monitoring recommendations
- Pre-flight checks before deployment
- LintRange or validation rules to add

## Related Playbooks

- [Related Playbook 1](../category/playbook-name.md) - Brief description
- [Related Playbook 2](../category/playbook-name.md) - Brief description

## Related Documentation

- [OPERATIONAL-PRINCIPLES.md](../OPERATIONAL-PRINCIPLES.md) - Stop/Analyze/Design workflow
- [CLAUDE.md](../CLAUDE.md) - GitOps workflow
- [Component Documentation](../CORTEX-COMPONENT-GUIDE.md) - Specific component details

## Real Examples

### Example 1: [Brief Description]
- **Date**: YYYY-MM-DD
- **Commit**: `abc123d` - Brief commit message
- **Issue**: What went wrong
- **Resolution**: How it was fixed
- **Session**: Link to debugging transcript if available

### Example 2: [Brief Description]
- **Date**: YYYY-MM-DD
- **Commit**: `def456a` - Brief commit message
- **Issue**: What went wrong
- **Resolution**: How it was fixed

---

## Usage Notes

**When to use this playbook**:
- Specific symptoms match
- Error messages contain keywords
- Related component showing issues

**When NOT to use this playbook**:
- Different symptoms present
- Refer to [Alternative Playbook](link) instead

**Escalation**:
- If playbook doesn't resolve issue within X attempts
- Consult [Advanced Troubleshooting](link) or seek expert assistance
