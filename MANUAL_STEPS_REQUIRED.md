# Manual Steps Required for MCP Infrastructure

This document outlines manual steps that must be completed by the user to fully operationalize the MCP infrastructure.

---

## 1. n8n API Key Generation

The n8n MCP server requires an API key to interact with the n8n instance.

### Steps:

1. Access n8n web interface at: `https://n8n.ry-ops.dev`

2. Navigate to **Settings → API**

3. Generate a new API key:
   - Click **"Create API Key"**
   - Give it a descriptive name: `MCP Server Integration`
   - Copy the generated key immediately (it won't be shown again)

4. Create Kubernetes Secret:
   ```bash
   kubectl create secret generic n8n-mcp-credentials \
     -n cortex-system \
     --from-literal=N8N_API_KEY='your-api-key-here'
   ```

5. Update the n8n MCP server deployment to use the secret:
   ```bash
   # Edit the deployment
   kubectl edit deployment n8n-mcp-server -n cortex-system

   # Add environment variable:
   env:
   - name: N8N_API_KEY
     valueFrom:
       secretKeyRef:
         name: n8n-mcp-credentials
         key: N8N_API_KEY
   ```

6. Restart the n8n MCP server:
   ```bash
   kubectl rollout restart deployment n8n-mcp-server -n cortex-system
   ```

---

## 2. CheckMK Automation User Creation

The CheckMK MCP server requires an automation user for API access.

### Steps:

1. Access CheckMK web interface at: `https://checkmk.ry-ops.dev`

2. Navigate to **Setup → Users → Users**

3. Create a new automation user:
   - Click **"Add user"**
   - Username: `mcp-automation`
   - Full name: `MCP Server Automation`
   - Select: **Automation user (technical user for scripted access)**
   - Set automation secret: Generate a strong random string
   - Roles: `admin` (or custom role with read access to all monitoring data)

4. Save the user

5. Create Kubernetes Secret:
   ```bash
   kubectl create secret generic checkmk-mcp-credentials \
     -n cortex-system \
     --from-literal=CHECKMK_USERNAME='mcp-automation' \
     --from-literal=CHECKMK_SECRET='your-automation-secret-here'
   ```

6. Update the CheckMK MCP server deployment:
   ```bash
   # Edit the deployment
   kubectl edit deployment checkmk-mcp-server -n cortex-system

   # Add environment variables:
   env:
   - name: CHECKMK_USERNAME
     valueFrom:
       secretKeyRef:
         name: checkmk-mcp-credentials
         key: CHECKMK_USERNAME
   - name: CHECKMK_SECRET
     valueFrom:
       secretKeyRef:
         name: checkmk-mcp-credentials
         key: CHECKMK_SECRET
   ```

7. Restart the CheckMK MCP server:
   ```bash
   kubectl rollout restart deployment checkmk-mcp-server -n cortex-system
   ```

---

## 3. Cloudflare API Token (Optional)

If Cloudflare MCP server is being used, it requires an API token.

### Steps:

1. Log into Cloudflare dashboard: `https://dash.cloudflare.com`

2. Navigate to **Profile → API Tokens**

3. Create a new token:
   - Click **"Create Token"**
   - Use template: **"Edit zone DNS"** or create custom token
   - Permissions needed:
     - Zone → DNS → Read
     - Zone → Zone → Read
     - (Add others as needed for your use case)
   - Zone Resources: **Include → Specific zone → (select your domain)**

4. Copy the token

5. Create Kubernetes Secret:
   ```bash
   kubectl create secret generic cloudflare-mcp-credentials \
     -n cortex-system \
     --from-literal=CLOUDFLARE_API_TOKEN='your-token-here'
   ```

6. Update the Cloudflare MCP server deployment:
   ```bash
   # Edit the deployment
   kubectl edit deployment cloudflare-mcp-server -n cortex-system

   # Add environment variable:
   env:
   - name: CLOUDFLARE_API_TOKEN
     valueFrom:
       secretKeyRef:
         name: cloudflare-mcp-credentials
         key: CLOUDFLARE_API_TOKEN
   ```

7. Restart the Cloudflare MCP server:
   ```bash
   kubectl rollout restart deployment cloudflare-mcp-server -n cortex-system
   ```

---

## 4. Address Memory Pressure Issues

The cluster is currently experiencing memory pressure causing pods to fail scheduling.

### Current Status (from quick fixes script):

```
k3s-master03   81% memory usage
k3s-worker04   74% memory usage
k3s-master02   67% memory usage
```

### Immediate Actions:

1. **Scale down non-critical workloads** (temporary):
   ```bash
   # Example: Scale down development master if not actively used
   kubectl scale deployment development-master -n cortex-system --replicas=0

   # Scale down other non-essential services
   kubectl scale deployment <service-name> -n <namespace> --replicas=0
   ```

2. **Review and optimize resource requests**:
   - Many MCP servers are set to `128Mi` requests but may need less
   - Consider reducing limits for low-traffic servers

3. **Long-term solutions**:
   - Add more worker nodes to the cluster
   - Upgrade existing nodes with more memory
   - Implement pod priority classes to ensure critical pods schedule first
   - Use Horizontal Pod Autoscaler (HPA) to scale based on actual usage

### Priority Pods Currently Pending:

```
- kubernetes-mcp-server (pending 10+ hours)
- n8n-mcp-server (pending 10+ hours)
- checkmk-mcp-server (just created, pending)
- cloudflare-mcp-server (pending)
- proxmox-mcp-server (pending)
- sandfly-mcp-server (pending)
```

### Recommended Action:

Run the memory optimization analysis:
```bash
# See which pods are using the most memory
kubectl top pods -A --sort-by=memory | head -20

# Identify candidates for scaling down
kubectl get deployments -A -o json | \
  jq -r '.items[] | select(.spec.replicas > 0) | "\(.metadata.namespace)/\(.metadata.name) - \(.spec.replicas) replicas"'
```

---

## 5. Verify ArgoCD Sync

After making changes, verify ArgoCD synchronization:

```bash
# Check sync status
kubectl get application cortex-system -n argocd

# Force sync if needed (only if auto-sync fails)
kubectl patch application cortex-system -n argocd \
  --type merge -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'

# Watch sync progress
kubectl get application cortex-system -n argocd -w
```

---

## 6. Validate MCP Server Health

After completing the above steps, validate all MCP servers are healthy:

```bash
# Run the quick fixes script
/Users/ryandahlberg/Projects/cortex-gitops/scripts/mcp-quick-fixes.sh

# Check individual server health endpoints
for server in unifi proxmox sandfly cloudflare checkmk kubernetes n8n; do
  echo "Checking ${server}-mcp-server..."
  kubectl exec -n cortex-system deploy/${server}-mcp-server -- \
    wget -qO- http://localhost:8080/health || echo "Failed"
done
```

---

## Summary Checklist

- [ ] Generate n8n API key and create secret
- [ ] Create CheckMK automation user and secret
- [ ] (Optional) Generate Cloudflare API token and secret
- [ ] Address cluster memory pressure
- [ ] Restart affected MCP server deployments
- [ ] Verify ArgoCD sync status
- [ ] Validate all MCP servers are healthy
- [ ] Test end-to-end functionality with cortex_query tool

---

## Support

For issues or questions:

1. Check pod logs: `kubectl logs -n cortex-system deployment/<mcp-server-name>`
2. Describe pod for events: `kubectl describe pod -n cortex-system <pod-name>`
3. Review ArgoCD application: `kubectl describe application cortex-system -n argocd`
4. Run quick fixes script: `/Users/ryandahlberg/Projects/cortex-gitops/scripts/mcp-quick-fixes.sh`

---

**Last Updated**: 2026-01-12
**Version**: 1.0.0
