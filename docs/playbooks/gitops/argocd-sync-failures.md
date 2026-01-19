# Playbook: ArgoCD Sync Failures
**Category**: GitOps
**Last Updated**: 2026-01-18
**Severity**: High

---

## Symptoms

- ArgoCD Application shows "OutOfSync" or "Unknown" status
- Application health status shows "Degraded" or "Progressing"
- Sync errors in ArgoCD UI or `kubectl describe`
- Changes pushed to Git but not reflected in cluster
- Error messages: "ComparisonError", "failed to generate manifest", "failed to list refs"

## Quick Diagnosis

```bash
# Check Application sync status
kubectl get applications -n argocd
# Look for: SYNC STATUS = OutOfSync/Unknown, HEALTH = Degraded

# Get detailed Application status
kubectl get application <app-name> -n argocd -o jsonpath='{.status.sync.status}'

# Check for sync errors
kubectl describe application <app-name> -n argocd | grep -A 10 "Conditions:"
```

## Investigation Steps

### 1. Check Application Sync Status

**Command**:
```bash
kubectl describe application <app-name> -n argocd
```

**What to Look For**:
- **Conditions**: Error messages explaining sync failure
- **Sync Status**: OutOfSync reasons
- **Operation State**: Last sync attempt result
- **Resources**: Which resources failed to sync

### 2. Check ArgoCD Can Reach GitHub

**Command**:
```bash
# Check repo-server logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-repo-server --tail=50

# Look for: Git clone/fetch errors, authentication failures, network timeouts
```

**Common Errors**:
- `failed to list refs`: Can't connect to Git repository
- `authentication required`: Missing or invalid credentials
- `dial tcp: i/o timeout`: Network connectivity to GitHub

### 3. Check Manifest Generation

**Command**:
```bash
# Check for YAML parsing errors
kubectl describe application <app-name> -n argocd | grep -A 5 "ComparisonError"
```

**What to Look For**:
- YAML syntax errors
- Invalid Kubernetes resource definitions
- Missing required fields

### 4. Verify Repository Configuration

**File to Check**: `argocd-apps/<app-name>.yaml`

**Command**:
```bash
kubectl get application <app-name> -n argocd -o yaml | grep -A 10 "source:"
```

**What to Look For**:
- Correct repository URL
- Valid branch/tag (targetRevision)
- Correct path to manifests

## Common Root Causes

### Cause A: Redis Connectivity Timeout

**Indicators**:
- Error: `dial tcp 10.43.233.191:6379: i/o timeout`
- ArgoCD Application status "Unknown"
- Sync hangs or times out

**Solution**:
1. Check Redis pod status:
   ```bash
   kubectl get pods -n argocd -l app.kubernetes.io/name=argocd-redis
   ```

2. If Redis not running, check deployment:
   ```bash
   kubectl get deployment argocd-redis -n argocd
   kubectl describe deployment argocd-redis -n argocd
   ```

3. Restart Redis if needed:
   ```bash
   kubectl rollout restart deployment/argocd-redis -n argocd
   ```

4. Force Application refresh:
   ```bash
   kubectl patch application <app-name> -n argocd \
     --type merge -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
   ```

**Verification**:
```bash
kubectl get application <app-name> -n argocd
# Status should update within 3 minutes
```

### Cause B: YAML Syntax Errors

**Indicators**:
- Error: `error converting YAML to JSON`
- Error: `yaml: line X: could not find expected ':'`
- ComparisonError in Application status

**Solution**:
1. Review recent commits for YAML changes:
   ```bash
   git log --oneline -5 apps/<namespace>/
   ```

2. Validate YAML syntax:
   ```bash
   kubectl apply --dry-run=client -f apps/<namespace>/<file>.yaml
   ```

3. Common YAML issues:
   - Incorrect indentation
   - Missing quotes around special characters
   - Embedded code (Python f-strings, etc.) in ConfigMaps
   - Frontmatter in markdown fields

4. Fix YAML and commit:
   ```bash
   # Edit file to fix syntax
   git add apps/<namespace>/<file>.yaml
   git commit -m "Fix YAML syntax error in <file>"
   git push origin main
   ```

**Verification**:
```bash
# ArgoCD will auto-sync within 3 minutes
kubectl get application <app-name> -n argocd
# SYNC STATUS should become "Synced"
```

### Cause C: Manual kubectl apply Drift

**Indicators**:
- Application "OutOfSync" even though Git is up-to-date
- Resources marked "Requires Pruning: true"
- Manual changes made directly with kubectl

**Solution**:
1. Check which resources are out of sync:
   ```bash
   kubectl describe application <app-name> -n argocd | grep "Requires Pruning"
   ```

2. **Option 1**: Let ArgoCD auto-heal (if enabled):
   - Wait up to 3 minutes for auto-sync
   - Self-heal will revert manual changes

3. **Option 2**: Manually sync Application:
   ```bash
   # Sync with prune (removes manually created resources)
   kubectl patch application <app-name> -n argocd \
     --type merge -p '{"operation":{"sync":{"prune":true}}}'
   ```

4. **Option 3**: Update Git to match cluster:
   - Export current cluster state
   - Update manifests in Git
   - Commit changes

**Prevention**: Never use `kubectl apply` directly. Always update Git → ArgoCD → Cluster.

**Verification**:
```bash
kubectl get application <app-name> -n argocd
# SYNC STATUS = Synced
```

### Cause D: Repository Authentication Failure

**Indicators**:
- Error: `authentication required: Repository not found`
- Error: `remote: Repository not found`
- Private repository access issues

**Solution**:
1. Check repository secret exists:
   ```bash
   kubectl get secrets -n argocd | grep repo
   ```

2. If using HTTPS with token, update secret:
   ```bash
   kubectl create secret generic repo-<name> \
     --from-literal=url=https://github.com/user/repo \
     --from-literal=username=<username> \
     --from-literal=password=<token> \
     -n argocd --dry-run=client -o yaml | kubectl apply -f -
   ```

3. Add label to secret:
   ```bash
   kubectl label secret repo-<name> -n argocd \
     argocd.argoproj.io/secret-type=repository
   ```

**Verification**:
```bash
# Trigger refresh
kubectl patch application <app-name> -n argocd \
  --type merge -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
```

## Prevention

- **Validate YAML before committing**: Use `kubectl apply --dry-run=client`
- **Monitor ArgoCD health**: Check Application status regularly
- **Never manual kubectl apply**: Always commit to Git first
- **Test in dev namespace**: Validate changes before production
- **Enable auto-sync**: Let ArgoCD handle sync automatically
- **Use pre-commit hooks**: Validate YAML syntax in Git hooks

## Related Playbooks

- [Kaniko Build Timeouts](./kaniko-build-timeouts.md) - Image build issues
- [YAML Syntax Errors](../general/yaml-validation.md) - Manifest validation

## Related Documentation

- [CLAUDE.md](../../CLAUDE.md#gitops-workflow) - GitOps workflow (Git → ArgoCD → Cluster)
- [OPERATIONAL-PRINCIPLES.md](../../OPERATIONAL-PRINCIPLES.md) - No manual deployments

## Real Examples

### Example 1: cortex-chat ArgoCD Redis Timeout
- **Date**: 2026-01-18
- **Commit**: `c07013e` - Convert chat services from LoadBalancer to NodePort
- **Issue**: Application status "Unknown", sync failing
- **Error**: `failed to generate manifest: dial tcp 10.43.233.191:6379: i/o timeout`
- **Root Cause**: ArgoCD Redis connection timeout preventing manifest comparison
- **Impact**: Services marked "Requires Pruning: true", changes not syncing
- **Resolution**: Manually applied changes with `kubectl apply -f` to bypass ArgoCD
- **Workaround**: Direct kubectl apply (not ideal, violates GitOps)
- **Proper Fix**: Restart ArgoCD Redis, force refresh Application

### Example 2: MoE Router YAML Syntax Error
- **Date**: 2026-01-18 (from session summary)
- **Issue**: `error parsing moe-router-build-job.yaml`
- **Error**: `error converting YAML to JSON: yaml: line 94: could not find expected ':'`
- **Root Cause**: Python code embedded in ConfigMap with f-strings and dict notation that YAML parser interpreted as YAML syntax
- **Example**:
  ```yaml
  data:
    code: |
      def classify(message: str) -> dict:
        """Returns: {expert: str, confidence: float}"""  # YAML saw this as mapping
  ```
- **Resolution**: Changed docstring to plain text, moved to inline RUN command approach
- **Lesson**: Avoid complex code in YAML ConfigMaps, use separate files or escape properly

---

## Usage Notes

**When to use this playbook**:
- ArgoCD Application shows OutOfSync/Unknown status
- Changes committed to Git but not appearing in cluster
- Sync errors in ArgoCD logs or UI
- Resources stuck in "Requires Pruning" state

**When NOT to use this playbook**:
- Application Synced but pods crashing → See [CrashLoop BackOff](../pod-debugging/crashloop-backoff.md)
- Application Synced but service unreachable → See [Service Connectivity](../network/service-connectivity.md)
- Git repository not accessible at all → Check GitHub status or network

**Escalation**:
- If Redis timeouts persist → Check ArgoCD resource limits
- If YAML valid but still fails → Check ArgoCD version compatibility
- If all Applications failing → Check ArgoCD controller logs for systemic issues
