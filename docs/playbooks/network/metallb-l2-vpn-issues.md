# Playbook: MetalLB L2 Mode Over VPN Issues
**Category**: Network
**Last Updated**: 2026-01-18
**Severity**: Medium

---

## Symptoms

- LoadBalancer services get External-IP assigned but are unreachable
- Ping to Metal LB IP pool addresses (10.88.145.200-220) times out
- Services accessible from cluster nodes but not from remote VPN clients
- Browser/client connection timeout when accessing LoadBalancer services
- MetalLB speaker pods running but ARP not working across network

## Quick Diagnosis

```bash
# Check LoadBalancer services and assigned IPs
kubectl get svc -A | grep LoadBalancer
# Expected output showing EXTERNAL-IP assigned:
# cortex-chat-frontend   LoadBalancer   10.43.212.144   10.88.145.210   80:32308/TCP

# Test connectivity from local machine
ping -c 3 10.88.145.200
# If 100% packet loss → MetalLB L2/VPN issue

# Check if cluster nodes are reachable
ping -c 3 10.88.145.190
# If successful → routing works, issue is MetalLB L2 mode
```

## Investigation Steps

### 1. Verify MetalLB Configuration

**Files to Check**:
- MetalLB IP pool configuration
- L2Advertisement settings

**Commands**:
```bash
# Check IP address pools
kubectl get ipaddresspools -n metallb-system
# Expected: Pool with IP range like 10.88.145.200-10.88.145.220

# Check L2 advertisements
kubectl get l2advertisements -n metallb-system
# Expected: L2Advertisement resource exists

# Get detailed config
kubectl get ipaddresspool -n metallb-system default-pool -o yaml
kubectl get l2advertisement -n metallb-system default -o yaml
```

**What to Look For**:
- IP pool matches allocated External-IPs
- L2Advertisement is configured for the pool
- No BGP configuration (would indicate different mode)

### 2. Check MetalLB Speaker Pods

**Command**:
```bash
# Check speaker pods running on all nodes
kubectl get pods -n metallb-system -o wide
```

**What to Look For**:
- Speaker pods running on each cluster node (DaemonSet)
- All speakers in `Running` status
- Speakers distributed across nodes

**Expected Output**:
```
NAME                         READY   STATUS    RESTARTS   AGE   NODE
controller-bb5f47665-2h75r   1/1     Running   1          7d    k3s-worker02
speaker-hzscq                1/1     Running   1          23h   k3s-master03
speaker-kp72j                1/1     Running   1          23h   k3s-worker02
speaker-lw7ft                1/1     Running   1          23h   k3s-worker01
...
```

### 3. Test Network Reachability

**From local machine (VPN client)**:
```bash
# Test cluster node IPs (should work)
ping -c 2 10.88.145.190  # Master node
ping -c 2 10.88.145.195  # Worker node

# Test MetalLB LoadBalancer IPs (will fail with L2/VPN)
ping -c 2 10.88.145.200  # Traefik LoadBalancer
ping -c 2 10.88.145.210  # Chat frontend LoadBalancer
```

**Check routing table**:
```bash
netstat -rn | grep "10.88"
# Should show route to 10.88.145.0/24 via VPN interface (utun6, etc.)
```

**What to Look For**:
- Cluster node IPs reachable → Layer 3 routing works
- LoadBalancer IPs unreachable → Layer 2 ARP issue
- Route exists but packets dropped → L2/L3 boundary problem

### 4. Understand the Root Cause

**Network Architecture Analysis**:

```
┌─────────────────────────────────────────────┐
│  Local Machine (VPN Client)                 │
│  IP: 100.x.x.x (Tailscale)                  │
└──────────────┬──────────────────────────────┘
               │ Layer 3 (IP Routing)
               │ utun6 interface
               ▼
┌─────────────────────────────────────────────┐
│  K3s Cluster Nodes (10.88.145.190-196)      │
│  ✓ Reachable via routed VPN                 │
└──────────────┬──────────────────────────────┘
               │
               │ Layer 2 (ARP - Local Broadcast)
               ▼
┌─────────────────────────────────────────────┐
│  MetalLB LoadBalancer IPs (10.88.145.200+)  │
│  ✗ NOT reachable - ARP can't cross L3       │
└─────────────────────────────────────────────┘
```

**Why L2 Mode Doesn't Work**:
- MetalLB L2 mode uses ARP (Address Resolution Protocol)
- ARP is a Layer 2 broadcast protocol
- VPNs (Tailscale, WireGuard, etc.) are Layer 3 routed networks
- ARP broadcasts don't cross Layer 3 boundaries
- RFC 826 limitation: ARP requires same broadcast domain

## Common Root Causes

### Cause A: MetalLB L2 Mode Over Routed VPN (Most Common)

**Indicators**:
- Cluster nodes reachable, LoadBalancer IPs unreachable
- VPN uses routed (Layer 3) connectivity
- MetalLB configured with L2Advertisement
- No BGP configuration

**Solution Option 1: Switch to NodePort Services**

This is the recommended solution for VPN access.

1. Identify affected services:
   ```bash
   kubectl get svc -A | grep LoadBalancer
   ```

2. Convert service type from LoadBalancer to NodePort:

   **Edit file**: `apps/<namespace>/<service-name>-service.yaml`

   Change:
   ```yaml
   spec:
     type: LoadBalancer
     loadBalancerIP: 10.88.145.210
   ```

   To:
   ```yaml
   spec:
     type: NodePort
     # Optionally specify nodePort:
     # ports:
     # - port: 80
     #   nodePort: 32308
   ```

3. Commit and push changes:
   ```bash
   git add apps/<namespace>/<service-name>-service.yaml
   git commit -m "Convert <service> from LoadBalancer to NodePort for VPN access"
   git push origin main
   ```

4. Or apply directly (bypass ArgoCD):
   ```bash
   kubectl apply -f apps/<namespace>/<service-name>-service.yaml
   ```

5. Get assigned NodePort:
   ```bash
   kubectl get svc <service-name> -n <namespace>
   # Look for PORT(S) column: 80:32308/TCP
   #                            ↑   ↑
   #                       port  NodePort
   ```

6. Access service via any cluster node IP + NodePort:
   ```bash
   curl http://10.88.145.190:32308
   # Or in browser: http://10.88.145.190:32308
   ```

**Files to Modify**:
- `apps/<namespace>/<service-name>-frontend-service.yaml`
- `apps/<namespace>/<service-name>-backend-service.yaml`
- Any other LoadBalancer services needing VPN access

**Verification**:
```bash
# Service should show NodePort
kubectl get svc -n <namespace>
# Expected: TYPE = NodePort, with port mapping like 80:32308/TCP

# Test access via node IP
curl -I http://10.88.145.190:<nodePort>
# Expected: HTTP 200 OK
```

**Solution Option 2: Switch MetalLB to BGP Mode** (Advanced)

Only use if you control network routing and can configure BGP.

**Requirements**:
- BGP router accessible from VPN network
- Ability to configure BGP peering
- Network allows BGP protocol (TCP 179)

**Not Recommended Because**:
- Requires network infrastructure changes
- More complex to maintain
- Overkill for VPN access
- NodePort is simpler and sufficient

**Solution Option 3: Use Port Forwarding** (Development/Debug Only)

For temporary access during debugging:

```bash
# Forward local port to service
kubectl port-forward -n <namespace> svc/<service-name> 8080:80

# Access on localhost
curl http://localhost:8080
```

**Limitations**:
- Only accessible from machine running port-forward
- Requires kubectl access
- Session-based (not persistent)
- Not suitable for production access

### Cause B: MetalLB on Separate Ingress Server (Misconfiguration)

**Indicators**:
- User expects MetalLB on dedicated ingress node (10.88.145.199)
- Ingress server not showing in `kubectl get nodes`
- MetalLB speakers running on K3s cluster nodes instead

**Solution**:
1. Understand MetalLB runs as part of K3s cluster (not separate server)
2. MetalLB speaker pods deployed as DaemonSet on cluster nodes
3. LoadBalancer IPs announced from cluster nodes, not separate hardware
4. If separate ingress server needed, use NodePort + external load balancer

**Verification**:
```bash
# Confirm MetalLB speakers are on cluster nodes
kubectl get pods -n metallb-system -o wide
# NODE column should show k3s-master/worker nodes
```

## Prevention

- **Document VPN limitations** when using MetalLB L2 mode
- **Default to NodePort** for services requiring VPN access
- **Use LoadBalancer** only for services accessed from local network (same L2 domain)
- **Consider ingress controllers** (Traefik, nginx) with NodePort for HTTP/HTTPS services
- **Test connectivity** from VPN before marking service "accessible"
- **Update /etc/hosts** to use NodePort-accessible IPs, not LoadBalancer IPs

## Related Playbooks

- [Service Connectivity Issues](./service-connectivity.md) - General service debugging
- [ArgoCD Sync Failures](../gitops/argocd-sync-failures.md) - If service changes don't sync

## Related Documentation

- [CLAUDE.md](../../CLAUDE.md#gitops-workflow) - GitOps workflow for service changes
- [Kubernetes Service Types](https://kubernetes.io/docs/concepts/services-networking/service/#publishing-services-service-types)
- [MetalLB L2 Mode](https://metallb.universe.tf/concepts/layer2/)

## Real Examples

### Example 1: cortex-chat LoadBalancer → NodePort Migration
- **Date**: 2026-01-18
- **Commit**: `c07013e` - Convert chat services from LoadBalancer to NodePort for VPN access
- **Issue**: chat.ry-ops.dev (10.88.145.200) unreachable from Tailscale VPN
- **Root Cause**: MetalLB L2 mode ARP doesn't cross routed VPN connection
- **Investigation**:
  - Verified cluster nodes reachable: `ping 10.88.145.190` ✓
  - MetalLB LoadBalancer IP unreachable: `ping 10.88.145.200` ✗
  - MetalLB config correct (L2Advertisement exists)
  - Network analysis: VPN is Layer 3, MetalLB L2 requires Layer 2
- **Resolution**:
  - Converted 3 services to NodePort:
    - `cortex-chat-service.yaml`: ClusterIP → NodePort
    - `cortex-chat-frontend-service.yaml`: LoadBalancer → NodePort (kept nodePort 32308)
    - `cortex-chat-backend-simple-service.yaml`: ClusterIP → NodePort
  - Removed LoadBalancer-specific fields (allocateLoadBalancerNodePorts, loadBalancerIP, externalTrafficPolicy)
  - Applied changes: `kubectl apply -f apps/cortex-chat/*service*.yaml`
- **Access Method**: http://10.88.145.190:32308 (any node IP + NodePort)
- **Verification**:
  ```bash
  curl -I http://10.88.145.190:32308
  # HTTP/1.1 200 OK
  # Server: nginx/1.25.5
  ```

### Example 2: Traefik Ingress Still Using LoadBalancer
- **Date**: 2026-01-18
- **Status**: Not yet converted
- **Current State**: Traefik service using LoadBalancer IP 10.88.145.200
- **Impact**: Ingress routing (chat.ry-ops.dev) not working over VPN
- **Pending Decision**: Convert Traefik to NodePort or access services directly via NodePorts

---

## Usage Notes

**When to use this playbook**:
- LoadBalancer services unreachable from VPN
- Ping to MetalLB IPs times out but cluster nodes reachable
- Accessing K3s services from Tailscale/WireGuard/OpenVPN
- MetalLB using L2 mode (default)

**When NOT to use this playbook**:
- Services unreachable from local network (same subnet) → Different issue
- All network connectivity failing → Check VPN/routing issues
- MetalLB using BGP mode → Different troubleshooting path
- Services using ClusterIP → Not exposed externally at all

**Escalation**:
- If NodePort solution doesn't work → Check NodePort range configuration
- If must use LoadBalancer → Investigate BGP mode or L2-aware VPN
- If network policies block NodePort → Review NetworkPolicy rules
