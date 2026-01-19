# Playbook: Kaniko Build Timeouts
**Category**: GitOps
**Last Updated**: 2026-01-18
**Severity**: High

---

## Symptoms

- Kaniko build jobs fail or timeout
- Error: `dial tcp 10.43.170.72:5000: i/o timeout`
- Error: `error checking push permissions`
- Images not appearing in registry after build job completes
- Build job pods stuck in Running state beyond expected duration

## Quick Diagnosis

```bash
# Check build jobs status
kubectl get jobs -n <namespace> --sort-by=.metadata.creationTimestamp
# Look for: COMPLETIONS = 0/1, duration > 10 minutes

# Check job pod status
kubectl get pods -n <namespace> -l job-name=<build-job-name>

# View build logs
kubectl logs -n <namespace> -l job-name=<build-job-name> --tail=50
# Look for: timeout errors, registry connection failures
```

## Investigation Steps

### 1. Check Build Job Status and Logs

**Command**:
```bash
# Get job details
kubectl describe job <build-job-name> -n <namespace>

# Get full build logs
kubectl logs -n <namespace> job/<build-job-name>
```

**What to Look For**:
- Last log line indicates where build stopped
- Network timeout errors
- Registry push failures
- Source code fetch errors (Git clone failures)

### 2. Verify Docker Registry is Running

**Command**:
```bash
# Check registry pod
kubectl get pods -n cortex-chat -l app=docker-registry

# Check registry service
kubectl get svc docker-registry -n cortex-chat

# Test registry health
kubectl exec -n cortex-chat $(kubectl get pod -n cortex-chat -l app=docker-registry -o name) -- \
  wget -qO- http://localhost:5000/v2/_catalog
```

**What to Look For**:
- Pod status: Running (1/1 Ready)
- Service has endpoints assigned
- Registry responds with catalog (even if empty: `{"repositories":[]}`)

### 3. Test Registry Connectivity from Build Pod

**Command**:
```bash
# Get build pod name
BUILD_POD=$(kubectl get pods -n <namespace> -l job-name=<build-job-name> -o name)

# Test registry connectivity
kubectl exec -n <namespace> $BUILD_POD -- \
  wget --spider http://10.43.170.72:5000/v2/

# Or use curl if available
kubectl exec -n <namespace> $BUILD_POD -- \
  curl -I http://10.43.170.72:5000/v2/
```

**Expected Response**: HTTP 200 OK or 401 (if auth required)
**If Timeout**: Registry not reachable from build pod

### 4. Check Network Policies

**Command**:
```bash
# List network policies in namespace
kubectl get networkpolicy -n <namespace>

# Check if policy blocks registry traffic
kubectl describe networkpolicy <policy-name> -n <namespace>
```

**What to Look For**:
- Ingress/egress rules blocking port 5000
- Rules not allowing traffic to docker-registry service
- Namespace isolation preventing cross-namespace communication

## Common Root Causes

### Cause A: Registry Service Unreachable (Most Common)

**Indicators**:
- Error: `dial tcp 10.43.170.72:5000: i/o timeout`
- Registry pod running but service not responding
- Intermittent timeouts (works sometimes, fails others)

**Solution**:
1. Check registry pod health:
   ```bash
   kubectl get pods -n cortex-chat -l app=docker-registry
   ```

2. If pod not running, check deployment:
   ```bash
   kubectl describe deployment docker-registry -n cortex-chat
   ```

3. Restart registry pod:
   ```bash
   kubectl rollout restart deployment/docker-registry -n cortex-chat
   ```

4. Verify service endpoints:
   ```bash
   kubectl get endpoints docker-registry -n cortex-chat
   # Should show pod IP(s)
   ```

5. Test connectivity again:
   ```bash
   kubectl run -it --rm test --image=busybox --restart=Never -- \
     wget --spider http://10.43.170.72:5000/v2/
   ```

**Files to Check**: `apps/cortex-chat/docker-registry-deployment.yaml`

**Verification**:
```bash
# Registry should respond
curl http://10.43.170.72:5000/v2/_catalog
# Expected: {"repositories":[...]}

# Re-run build job
kubectl delete job <build-job-name> -n <namespace>
kubectl apply -f apps/<namespace>/<build-job>.yaml
```

### Cause B: Network Policy Blocking Traffic

**Indicators**:
- Registry service exists and responds to local requests
- Build pod can't reach registry
- Other pods in namespace also can't reach registry

**Solution**:
1. Check network policies:
   ```bash
   kubectl get networkpolicy -n <namespace> -o yaml
   ```

2. Add egress rule to allow registry traffic:
   ```yaml
   # In apps/<namespace>/network-policy.yaml
   spec:
     egress:
     - to:
       - namespaceSelector:
           matchLabels:
             name: cortex-chat
       ports:
       - protocol: TCP
         port: 5000
   ```

3. Apply changes:
   ```bash
   git add apps/<namespace>/network-policy.yaml
   git commit -m "Allow egress to docker-registry on port 5000"
   git push origin main
   ```

**Verification**:
```bash
# Test from build pod
kubectl exec -n <namespace> <build-pod> -- wget --spider http://10.43.170.72:5000/v2/
# Expected: HTTP response (not timeout)
```

### Cause C: GitHub Repository Access Failure

**Indicators**:
- Error: `authentication required: Repository not found`
- Error: `failed to resolve source context`
- Build fails before reaching registry push stage
- Using `git://` context in Kaniko

**Solution**:
1. Check Kaniko git context configuration:
   ```yaml
   # In apps/<namespace>/<build-job>.yaml
   args:
   - "--context=git://github.com/<org>/<repo>.git#<branch>:/<path>"
   ```

2. **For private repos**, add Git credentials:
   ```bash
   kubectl create secret generic git-creds \
     --from-literal=username=<github-username> \
     --from-literal=password=<github-token> \
     -n <namespace>
   ```

3. Mount credentials in Kaniko pod:
   ```yaml
   volumeMounts:
   - name: git-creds
     mountPath: /kaniko/.git-credentials
   volumes:
   - name: git-creds
     secret:
       secretName: git-creds
   ```

4. **Alternative**: Use ConfigMap-based build (embed Dockerfile):
   ```yaml
   # Create ConfigMap with Dockerfile
   apiVersion: v1
   kind: ConfigMap
   metadata:
     name: <app>-build
   data:
     Dockerfile: |
       FROM python:3.11-slim
       WORKDIR /app
       RUN pip install flask
       COPY app.py .
       CMD ["python", "app.py"]
   ---
   # Kaniko job uses ConfigMap
   args:
   - "--dockerfile=/workspace/Dockerfile"
   - "--context=dir:///workspace"
   volumeMounts:
   - name: dockerfile
     mountPath: /workspace
   volumes:
   - name: dockerfile
     configMap:
       name: <app>-build
   ```

**Files to Modify**: `apps/<namespace>/<build-job>.yaml`

**Verification**:
```bash
kubectl logs -n <namespace> job/<build-job-name>
# Should show: Successfully pulled source, building image...
```

### Cause D: Registry Disk Space Full

**Indicators**:
- First builds succeed, later builds fail
- Registry pod running but slow/unresponsive
- Error: `no space left on device` in registry logs

**Solution**:
1. Check registry logs:
   ```bash
   kubectl logs -n cortex-chat -l app=docker-registry
   ```

2. Check PVC usage (if using persistent storage):
   ```bash
   kubectl get pvc -n cortex-chat
   kubectl exec -n cortex-chat $(kubectl get pod -n cortex-chat -l app=docker-registry -o name) -- df -h
   ```

3. Clean up old images:
   ```bash
   # List all images
   kubectl exec -n cortex-chat $(kubectl get pod -n cortex-chat -l app=docker-registry -o name) -- \
     wget -qO- http://localhost:5000/v2/_catalog

   # Delete unused images (manual registry API calls or garbage collection)
   ```

4. Increase PVC size (if using persistent volume):
   ```yaml
   # In apps/cortex-chat/docker-registry-pvc.yaml
   spec:
     resources:
       requests:
         storage: 20Gi  # Increase from 10Gi
   ```

**Verification**:
```bash
# Check available space
kubectl exec -n cortex-chat $(kubectl get pod -n cortex-chat -l app=docker-registry -o name) -- df -h /var/lib/registry
```

## Prevention

- **Monitor registry health**: Set up alerts for registry pod restarts
- **Resource limits**: Ensure registry has adequate CPU/memory
- **Network policies**: Document required egress rules for builds
- **Build job cleanup**: Set `ttlSecondsAfterFinished` to clean up old jobs
- **Registry maintenance**: Periodic cleanup of unused images
- **Use ConfigMap builds**: Avoids GitHub auth issues for simple builds
- **Test registry before builds**: Verify connectivity before starting builds

## Related Playbooks

- [Image Pull Failures](../pod-debugging/image-pull-failures.md) - After build succeeds
- [ArgoCD Sync Failures](./argocd-sync-failures.md) - Build job manifest issues
- [Network Connectivity](../network/service-connectivity.md) - General network debugging

## Related Documentation

- [CLAUDE.md](../../CLAUDE.md) - GitOps workflow
- [Kaniko Documentation](https://github.com/GoogleContainerTools/kaniko)

## Real Examples

### Example 1: MoE Router Build Registry Timeout
- **Date**: 2026-01-18
- **Issue**: Multiple Kaniko builds timing out on registry push
- **Error**: `error checking push permissions: Get "https://10.43.170.72:5000/v2/": dial tcp 10.43.170.72:5000: i/o timeout`
- **Timeline**:
  - First build (with anthropic==0.39.0): Succeeded
  - Subsequent builds (with anthropic==0.50.0): Timed out
  - Registry connectivity degraded after initial build
- **Investigation**:
  - Registry pod showing as Running (1/1)
  - Service exists with ClusterIP 10.43.170.72
  - Build pods can't connect to registry
- **Status**: Unresolved - registry networking issue
- **Workaround**: Using simplified build with working older version
- **Next Steps**: Restart registry, test connectivity, investigate network policies

### Example 2: MoE Router GitHub Auth Failure
- **Date**: 2026-01-18 (from session summary)
- **Issue**: Kaniko build failing to clone from GitHub
- **Error**: `error resolving source context: authentication required: Repository not found`
- **Root Cause**: Using `git://` context for private repository without credentials
- **Original Config**:
  ```yaml
  args:
  - "--context=git://github.com/ry-ops/cortex-platform.git#main:/services/moe-router"
  ```
- **Resolution**: Switched to ConfigMap-based build with embedded Dockerfile
- **Lesson**: For private repos, either provide credentials or use ConfigMap/local context

### Example 3: Simplified MoE Router Build Success
- **Date**: 2026-01-18
- **Commit**: `moe-router-simple-build.yaml`
- **Approach**: ConfigMap with embedded Dockerfile and inline Python code
- **Status**: Build job created but hit registry timeout before push
- **Config**:
  ```yaml
  apiVersion: v1
  kind: ConfigMap
  data:
    Dockerfile: |
      FROM python:3.11-slim
      RUN pip install flask anthropic requests
      RUN printf '#!/usr/bin/env python3\n...' > app.py
      CMD ["python", "app.py"]
  ```
- **Advantage**: No GitHub auth needed, simplified build
- **Blocker**: Registry connectivity prevented completion

---

## Usage Notes

**When to use this playbook**:
- Kaniko build jobs failing or hanging
- Registry push timeouts
- Build images not appearing in registry
- GitHub clone failures in Kaniko context

**When NOT to use this playbook**:
- Image exists but pod can't pull → See [Image Pull Failures](../pod-debugging/image-pull-failures.md)
- Build completes but image is wrong → Check Dockerfile/build args
- Build fails on compilation errors → Check source code, not infrastructure

**Escalation**:
- If registry consistently unreachable → Consider external registry (Docker Hub, GHCR)
- If network policies complex → Review cluster network architecture
- If builds always timeout → Increase Kaniko job timeout, check node resources
