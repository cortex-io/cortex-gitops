# Playbook: Image Pull Failures
**Category**: Pod Debugging
**Last Updated**: 2026-01-18
**Severity**: High

---

## Symptoms

- Pod stuck in `ImagePullBackOff` or `ErrImagePull` status
- Pod shows `0/1 Ready` state
- Error messages mentioning image registry or pull failures
- Services unavailable due to missing container images

## Quick Diagnosis

```bash
# Check pod status
kubectl get pods -n <namespace>
# Expected output showing ImagePullBackOff:
# NAME                        READY   STATUS             RESTARTS   AGE
# my-app-5d9cf86b95-26kvf    0/1     ImagePullBackOff   0          10m

# Get detailed pod events
kubectl describe pod <pod-name> -n <namespace> | grep -A 10 "Events:"
# Look for: "Failed to pull image", "ErrImagePull", or specific error messages
```

## Investigation Steps

### 1. Check Pod Events for Error Details

**Command**:
```bash
kubectl describe pod <pod-name> -n <namespace> | grep -A 15 "Events:"
```

**What to Look For**:
- `Failed to pull image`: Image name and registry details
- `remote error: tls: handshake failure`: TLS/SSL issues with registry
- `failed to resolve reference`: Image doesn't exist or wrong name
- `dial tcp <ip>:<port>: i/o timeout`: Registry connectivity timeout
- `authentication required`: Missing ImagePullSecrets or wrong credentials

### 2. Verify Image Specification in Deployment

**File to Check**: `apps/<namespace>/<deployment-name>-deployment.yaml`

**Command**:
```bash
kubectl get deployment <deployment-name> -n <namespace> -o jsonpath='{.spec.template.spec.containers[*].image}'
```

**What to Look For**:
- Image name format: `registry/repository:tag`
- For internal registry: `10.43.170.72:5000/image-name:tag`
- For Docker Hub: `docker.io/library/image:tag` or `image:tag`
- Tag should exist (avoid `latest` if not guaranteed to exist)

### 3. Check Image Exists in Registry

**For Internal Registry (10.43.170.72:5000)**:
```bash
# List all images in registry
kubectl exec -n cortex-chat $(kubectl get pod -n cortex-chat -l app=docker-registry -o name) -- \
  wget -qO- http://localhost:5000/v2/_catalog

# Check specific image tags
kubectl exec -n cortex-chat $(kubectl get pod -n cortex-chat -l app=docker-registry -o name) -- \
  wget -qO- http://localhost:5000/v2/<image-name>/tags/list
```

**For External Registry**:
```bash
# Docker Hub
curl -s "https://registry.hub.docker.com/v2/repositories/library/<image-name>/tags/" | jq '.results[].name'

# GHCR
curl -s "https://ghcr.io/v2/<org>/<image-name>/tags/list" | jq '.tags'
```

### 4. Test Registry Connectivity from Node

**Command**:
```bash
# Get node name where pod is scheduled
NODE=$(kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.nodeName}')

# Test internal registry connectivity
kubectl exec -n cortex-chat $(kubectl get pod -n cortex-chat -l app=docker-registry -o name) -- \
  wget --spider http://10.43.170.72:5000/v2/

# Check if registry service is accessible
kubectl get svc docker-registry -n cortex-chat
```

### 5. Check Kaniko Build Jobs (if using internal registry)

**Command**:
```bash
# List recent build jobs
kubectl get jobs -n <namespace> --sort-by=.metadata.creationTimestamp

# Check latest build job status
kubectl describe job <build-job-name> -n <namespace>

# View build logs
kubectl logs -n <namespace> job/<build-job-name>
```

**What to Look For**:
- Job status: Completed vs Failed
- Build errors in logs
- Registry push errors
- Network timeout during push

## Common Root Causes

### Cause A: Image Doesn't Exist (Build Failed or Not Run)

**Indicators**:
- Events show: `failed to resolve reference` or `manifest unknown`
- Image not in registry catalog
- Kaniko build job shows Failed status

**Solution**:
1. Check if build job exists:
   ```bash
   kubectl get jobs -n <namespace> | grep build
   ```

2. If no build job, create one (check for `*-build*.yaml` or `*-kaniko*.yaml` files)

3. If build job failed, check logs:
   ```bash
   kubectl logs -n <namespace> job/<build-job-name>
   ```

4. Fix build errors (common issues: source code not found, Dockerfile syntax, dependency errors)

5. Delete failed job and re-run:
   ```bash
   kubectl delete job <build-job-name> -n <namespace>
   kubectl apply -f apps/<namespace>/<build-job>.yaml
   ```

**Files to Modify**: `apps/<namespace>/*-build*.yaml` or source repository

**Verification**:
```bash
# Check job completed
kubectl get job <build-job-name> -n <namespace>
# Expected: COMPLETIONS = 1/1

# Verify image in registry
kubectl exec -n cortex-chat $(kubectl get pod -n cortex-chat -l app=docker-registry -o name) -- \
  wget -qO- http://localhost:5000/v2/<image-name>/tags/list
# Expected: {"name":"<image-name>","tags":["latest"]}
```

### Cause B: Registry Connectivity Timeout

**Indicators**:
- Events show: `dial tcp 10.43.170.72:5000: i/o timeout`
- Registry service exists but unreachable
- Kaniko builds timing out on push

**Solution**:
1. Check registry pod is running:
   ```bash
   kubectl get pods -n cortex-chat -l app=docker-registry
   # Expected: STATUS = Running, READY = 1/1
   ```

2. If pod not running, check deployment:
   ```bash
   kubectl get deployment docker-registry -n cortex-chat
   kubectl describe deployment docker-registry -n cortex-chat
   ```

3. Check registry service endpoints:
   ```bash
   kubectl get svc docker-registry -n cortex-chat
   kubectl get endpoints docker-registry -n cortex-chat
   # Should show pod IP
   ```

4. Test connectivity from another pod:
   ```bash
   kubectl run -it --rm debug --image=busybox --restart=Never -- \
     wget --spider http://10.43.170.72:5000/v2/
   ```

5. If network policy exists, verify it allows traffic:
   ```bash
   kubectl get networkpolicy -n cortex-chat
   kubectl describe networkpolicy <policy-name> -n cortex-chat
   ```

**Files to Modify**:
- `apps/cortex-chat/docker-registry-deployment.yaml` (if pod issues)
- Network policies if blocking traffic

**Verification**:
```bash
# Registry should respond
curl -k http://10.43.170.72:5000/v2/_catalog
# Expected: {"repositories":[...]}
```

### Cause C: TLS Handshake Failure with External Registry

**Indicators**:
- Events show: `remote error: tls: handshake failure`
- Pulling from Docker Hub or external registry
- Node can't establish TLS connection

**Solution**:
1. **Temporary workaround** - Use internal registry or cached image

2. **Check node network/DNS**:
   ```bash
   # Get node name
   NODE=$(kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.nodeName}')

   # Check if node can resolve registry DNS
   kubectl debug node/$NODE -it --image=busybox -- nslookup registry-1.docker.io
   ```

3. **Alternative**: Use different image tag or mirror
   ```bash
   # Update deployment to use specific registry mirror
   # Edit apps/<namespace>/<deployment>.yaml
   # Change: image: nginx:1.25-alpine
   # To: image: docker.io/library/nginx:1.25-alpine
   ```

4. **Long-term fix**: Investigate node TLS certificate issues or firewall rules

**Files to Modify**: `apps/<namespace>/<deployment>.yaml` (change image source)

**Verification**:
```bash
kubectl get pods -n <namespace>
# Pod should pull successfully from alternative source
```

### Cause D: Missing or Invalid ImagePullSecrets

**Indicators**:
- Events show: `authentication required` or `unauthorized`
- Pulling from private registry
- 401 Unauthorized errors

**Solution**:
1. Check if ImagePullSecret exists:
   ```bash
   kubectl get secrets -n <namespace> | grep regcred
   ```

2. If missing, create ImagePullSecret:
   ```bash
   kubectl create secret docker-registry regcred \
     --docker-server=<registry-url> \
     --docker-username=<username> \
     --docker-password=<password> \
     --docker-email=<email> \
     -n <namespace>
   ```

3. Add ImagePullSecret to deployment:
   ```yaml
   # In apps/<namespace>/<deployment>.yaml
   spec:
     template:
       spec:
         imagePullSecrets:
         - name: regcred
   ```

4. Apply changes:
   ```bash
   kubectl apply -f apps/<namespace>/<deployment>.yaml
   ```

**Files to Modify**: `apps/<namespace>/<deployment>.yaml`

**Verification**:
```bash
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.imagePullSecrets}'
# Expected: [map[name:regcred]]
```

## Prevention

- **Use specific image tags** instead of `latest` to avoid confusion about which version exists
- **Verify build jobs complete** before deploying dependent services
- **Monitor registry health**: Ensure docker-registry pod stays running
- **Test image pulls** in development namespace before production deployment
- **Document build procedures** for each service with custom images
- **Use registry mirrors** for external images to avoid rate limiting and TLS issues
- **Set resource limits on registry** to prevent OOM kills: `apps/cortex-chat/docker-registry-deployment.yaml`

## Related Playbooks

- [Kaniko Build Timeouts](../gitops/kaniko-build-timeouts.md) - Registry connectivity during builds
- [CrashLoop BackOff](./crashloop-backoff.md) - Pod crashes after successful pull
- [Resource Quota Violations](../resources/limitrange-violations.md) - Pod scheduling issues

## Related Documentation

- [OPERATIONAL-PRINCIPLES.md](../../OPERATIONAL-PRINCIPLES.md) - Stop/Analyze/Design workflow
- [CLAUDE.md](../../CLAUDE.md) - GitOps workflow and deployment procedures

## Real Examples

### Example 1: cortex-chat-backend-simple ImagePullBackOff
- **Date**: 2026-01-18
- **Commit**: `a6b1a31` - Add nginx API proxy configuration for NodePort access
- **Issue**: Backend pod stuck in ImagePullBackOff. Image `10.43.170.72:5000/cortex-chat-backend-simple:latest` doesn't exist in registry.
- **Root Cause**: No build job exists for backend image, never been built
- **Resolution**: Need to create Kaniko build job for backend (pending)
- **Command Output**:
  ```
  cortex-chat-backend-simple-5d9cf86b95-26kvf   0/1     ImagePullBackOff   0      104m
  Events:
    Failed to pull image "10.43.170.72:5000/cortex-chat-backend-simple:latest":
    rpc error: code = Unknown desc = failed to pull and unpack image
  ```

### Example 2: cortex-chat Frontend TLS Handshake Failure
- **Date**: 2026-01-18
- **Commit**: `a6b1a31` - Add nginx API proxy configuration
- **Issue**: New frontend pod couldn't pull `nginx:1.25-alpine` from Docker Hub
- **Root Cause**: Node network TLS handshake failure with `registry-1.docker.io`
- **Resolution**: Kept existing pod running, avoided rollout
- **Command Output**:
  ```
  Failed to pull image "nginx:1.25-alpine":
  failed to pull and unpack image "docker.io/library/nginx:1.25-alpine":
  failed to do request: Head "https://registry-1.docker.io/v2/library/nginx/manifests/1.25-alpine":
  remote error: tls: handshake failure
  ```
- **Workaround**: Deleted failing new pod, kept old pod running with previous image

### Example 3: MoE Router Build Success Then Registry Timeout
- **Date**: 2026-01-18
- **Issue**: First Kaniko build succeeded with anthropic==0.39.0, subsequent builds timed out connecting to registry
- **Root Cause**: Registry connectivity degraded after initial build
- **Resolution**: Pending - need to investigate registry service health or use alternative registry
- **Session**: cortex-gitops debugging session (context compacted)

---

## Usage Notes

**When to use this playbook**:
- Pod shows ImagePullBackOff or ErrImagePull status
- Deployment events mention image pull failures
- New service won't start due to missing image

**When NOT to use this playbook**:
- Pod is Running but crashing → See [CrashLoop BackOff](./crashloop-backoff.md)
- Pod pending due to resources → See [Resource Violations](../resources/limitrange-violations.md)
- ArgoCD can't sync manifest → See [ArgoCD Sync Failures](../gitops/argocd-sync-failures.md)

**Escalation**:
- If registry consistently unreachable after 3 restart attempts
- If TLS errors persist across multiple nodes
- If image exists but can't be pulled (check cluster-wide network policies)
- Consider switching to external registry (Docker Hub, GHCR, ECR) as alternative
