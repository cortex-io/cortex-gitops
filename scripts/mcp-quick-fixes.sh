#!/bin/bash
# MCP Infrastructure Quick Fixes
# Implements quick wins identified in infrastructure review

set -e

echo "=== MCP Infrastructure Quick Fixes ==="
echo ""

# 1. Clean up Cloudflare crashloop pod
echo "1. Cleaning up Cloudflare crashloop pod..."
if kubectl get pod cloudflare-mcp-server-7cf88bccbc-lbbcc -n cortex-system &>/dev/null; then
  kubectl delete pod cloudflare-mcp-server-7cf88bccbc-lbbcc -n cortex-system
  echo "  ✓ Deleted crashloop pod"
else
  echo "  ✓ Pod already cleaned up"
fi
echo ""

# 2. Scale down old CheckMK revision
echo "2. Cleaning up old CheckMK revisions..."
OLD_CHECKMK_RS=$(kubectl get replicaset -n cortex-system 2>/dev/null | grep checkmk | grep -v "checkmk-0" | awk '{print $1}' || true)
if [ -n "$OLD_CHECKMK_RS" ]; then
  echo "  Found old ReplicaSets: $OLD_CHECKMK_RS"
  for rs in $OLD_CHECKMK_RS; do
    kubectl delete replicaset "$rs" -n cortex-system 2>/dev/null || echo "  Could not delete $rs"
  done
  echo "  ✓ Cleaned up old revisions"
else
  echo "  ✓ No old revisions to clean up"
fi
echo ""

# 3. Check if pending MCP servers can now schedule
echo "3. Checking pending MCP server pods..."
PENDING_PODS=$(kubectl get pods -n cortex-system 2>/dev/null | grep -E "(kubernetes|n8n|checkmk)-mcp-server" | grep Pending || true)
if [ -z "$PENDING_PODS" ]; then
  echo "  ✓ No pending pods!"
else
  echo "  ⚠ Found pending pods:"
  echo "$PENDING_PODS" | sed 's/^/    /'
  echo ""
  echo "  Showing pod events for pending pods:"
  kubectl get pods -n cortex-system | grep Pending | awk '{print $1}' | while read pod; do
    echo "    Events for $pod:"
    kubectl describe pod "$pod" -n cortex-system | grep -A 10 "Events:" | sed 's/^/      /'
  done
fi
echo ""

# 4. Verify new resource limits are applied
echo "4. Verifying resource limits..."
for server in unifi proxmox sandfly cloudflare; do
  echo "  - ${server}-mcp-server:"
  RESOURCES=$(kubectl get deployment "${server}-mcp-server" -n cortex-system -o jsonpath='{.spec.template.spec.containers[0].resources}' 2>/dev/null || echo "{}")
  if [ "$RESOURCES" != "{}" ]; then
    echo "$RESOURCES" | jq -r '
      "    Requests: CPU=" + (.requests.cpu // "not set") + ", Memory=" + (.requests.memory // "not set") + "\n" +
      "    Limits:   CPU=" + (.limits.cpu // "not set") + ", Memory=" + (.limits.memory // "not set")
    ' 2>/dev/null || echo "    Error parsing resources"
  else
    echo "    ✗ Deployment not found"
  fi
done
echo ""

# 5. Check overall cluster memory pressure
echo "5. Cluster memory status..."
if kubectl top nodes 2>/dev/null; then
  echo "  ✓ Cluster metrics available"
else
  echo "  ⚠ Metrics server not available or not responding"
fi
echo ""

# 6. Check ArgoCD sync status
echo "6. Checking ArgoCD sync status for cortex-system..."
if kubectl get application cortex-system -n argocd &>/dev/null; then
  SYNC_STATUS=$(kubectl get application cortex-system -n argocd -o jsonpath='{.status.sync.status}')
  HEALTH_STATUS=$(kubectl get application cortex-system -n argocd -o jsonpath='{.status.health.status}')
  echo "  Sync Status: $SYNC_STATUS"
  echo "  Health Status: $HEALTH_STATUS"

  if [ "$SYNC_STATUS" = "Synced" ] && [ "$HEALTH_STATUS" = "Healthy" ]; then
    echo "  ✓ Application is synced and healthy"
  else
    echo "  ⚠ Application needs attention"
  fi
else
  echo "  ✗ ArgoCD application not found"
fi
echo ""

# 7. Summary of MCP server pod status
echo "7. MCP Server Summary:"
echo ""
kubectl get pods -n cortex-system -l component=mcp-server -o custom-columns=\
NAME:.metadata.name,\
STATUS:.status.phase,\
READY:.status.containerStatuses[0].ready,\
RESTARTS:.status.containerStatuses[0].restartCount,\
AGE:.metadata.creationTimestamp 2>/dev/null || echo "  No MCP server pods found"
echo ""

echo "=== Quick Fixes Complete ==="
echo ""
echo "Summary:"
echo "  1. Cleaned up crashloop pods"
echo "  2. Removed old ReplicaSet revisions"
echo "  3. Checked for scheduling issues"
echo "  4. Verified resource limits"
echo "  5. Checked cluster memory"
echo "  6. Verified ArgoCD sync"
echo "  7. Displayed MCP server status"
echo ""
echo "Next Steps:"
echo "  - Review any pending pods above"
echo "  - Check MANUAL_STEPS_REQUIRED.md for credential setup"
echo "  - Monitor ArgoCD for auto-sync within 3 minutes"
