#!/bin/bash
# Phoenix Deployment Verification Script
# Purpose: Verify Phoenix LLM observability platform is deployed and operational

set -e

echo "=========================================="
echo "Phoenix LLM Observability - Verification"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check ArgoCD sync status
echo "1. Checking ArgoCD sync status..."
SYNC_STATUS=$(kubectl get application cortex-knowledge -n argocd -o jsonpath='{.status.sync.status}')
HEALTH_STATUS=$(kubectl get application cortex-knowledge -n argocd -o jsonpath='{.status.health.status}')

echo "   Sync Status: ${SYNC_STATUS}"
echo "   Health Status: ${HEALTH_STATUS}"

if [ "$SYNC_STATUS" == "Synced" ]; then
    echo -e "   ${GREEN}✓ ArgoCD synced successfully${NC}"
else
    echo -e "   ${YELLOW}⚠ Waiting for ArgoCD to sync (auto-sync enabled, checks every 3 minutes)${NC}"
fi
echo ""

# Check Phoenix deployment
echo "2. Checking Phoenix deployment..."
if kubectl get deployment phoenix -n cortex-knowledge &>/dev/null; then
    READY=$(kubectl get deployment phoenix -n cortex-knowledge -o jsonpath='{.status.readyReplicas}')
    DESIRED=$(kubectl get deployment phoenix -n cortex-knowledge -o jsonpath='{.spec.replicas}')
    echo "   Ready: ${READY}/${DESIRED}"

    if [ "$READY" == "$DESIRED" ]; then
        echo -e "   ${GREEN}✓ Phoenix deployment ready${NC}"
    else
        echo -e "   ${YELLOW}⚠ Waiting for Phoenix pod to be ready${NC}"
        kubectl get pods -n cortex-knowledge -l app=phoenix
    fi
else
    echo -e "   ${YELLOW}⚠ Phoenix deployment not yet created (waiting for ArgoCD)${NC}"
fi
echo ""

# Check Phoenix service
echo "3. Checking Phoenix service..."
if kubectl get service phoenix -n cortex-knowledge &>/dev/null; then
    CLUSTER_IP=$(kubectl get service phoenix -n cortex-knowledge -o jsonpath='{.spec.clusterIP}')
    echo "   Cluster IP: ${CLUSTER_IP}"
    echo "   Ports:"
    kubectl get service phoenix -n cortex-knowledge -o jsonpath='{range .spec.ports[*]}{"     "}{.name}{": "}{.port}{" -> "}{.targetPort}{"\n"}{end}'
    echo -e "   ${GREEN}✓ Phoenix service created${NC}"
else
    echo -e "   ${YELLOW}⚠ Phoenix service not yet created${NC}"
fi
echo ""

# Check Phoenix ingress
echo "4. Checking Phoenix ingress..."
if kubectl get ingress phoenix -n cortex-knowledge &>/dev/null; then
    HOST=$(kubectl get ingress phoenix -n cortex-knowledge -o jsonpath='{.spec.rules[0].host}')
    echo "   Host: ${HOST}"
    echo "   URL: https://${HOST}"

    # Check TLS certificate
    if kubectl get certificate phoenix-tls -n cortex-knowledge &>/dev/null; then
        CERT_READY=$(kubectl get certificate phoenix-tls -n cortex-knowledge -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')
        if [ "$CERT_READY" == "True" ]; then
            echo -e "   ${GREEN}✓ TLS certificate ready${NC}"
        else
            echo -e "   ${YELLOW}⚠ TLS certificate provisioning (may take 1-2 minutes)${NC}"
        fi
    fi
    echo -e "   ${GREEN}✓ Phoenix ingress created${NC}"
else
    echo -e "   ${YELLOW}⚠ Phoenix ingress not yet created${NC}"
fi
echo ""

# Check database initialization job
echo "5. Checking database initialization..."
if kubectl get job phoenix-db-init -n cortex-knowledge &>/dev/null; then
    SUCCEEDED=$(kubectl get job phoenix-db-init -n cortex-knowledge -o jsonpath='{.status.succeeded}')
    if [ "$SUCCEEDED" == "1" ]; then
        echo -e "   ${GREEN}✓ Database initialization completed${NC}"

        # Verify database exists
        echo "   Verifying 'phoenix' database exists..."
        if kubectl exec -it -n cortex-system postgres-0 -- psql -U postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'phoenix'" 2>/dev/null | grep -q 1; then
            echo -e "   ${GREEN}✓ Database 'phoenix' exists${NC}"
        else
            echo -e "   ${RED}✗ Database 'phoenix' not found${NC}"
        fi
    else
        echo -e "   ${YELLOW}⚠ Database initialization job running${NC}"
        kubectl get pods -n cortex-knowledge -l app=phoenix,component=db-init
    fi
else
    echo -e "   ${YELLOW}⚠ Database initialization job not yet created${NC}"
fi
echo ""

# Check Phoenix logs (if pod exists)
echo "6. Checking Phoenix logs..."
if kubectl get pods -n cortex-knowledge -l app=phoenix 2>/dev/null | grep -q Running; then
    echo "   Recent logs:"
    kubectl logs -n cortex-knowledge -l app=phoenix --tail=10 | sed 's/^/     /'
else
    echo -e "   ${YELLOW}⚠ Phoenix pod not yet running${NC}"
fi
echo ""

# Summary
echo "=========================================="
echo "Summary"
echo "=========================================="

if [ "$SYNC_STATUS" == "Synced" ] && [ "$HEALTH_STATUS" == "Healthy" ]; then
    echo -e "${GREEN}✓ Phoenix deployment complete and healthy${NC}"
    echo ""
    echo "Access Phoenix UI at: https://observability.ry-ops.dev"
    echo ""
    echo "OTLP Endpoint (for agents):"
    echo "  http://phoenix.cortex-knowledge.svc.cluster.local:4317"
    echo ""
    echo "Next Steps:"
    echo "  1. Verify UI is accessible: open https://observability.ry-ops.dev"
    echo "  2. Integrate with Python agent framework (see PHOENIX-INTEGRATION.md)"
    echo "  3. Configure dashboards (performance, cost, errors, chains)"
elif [ "$SYNC_STATUS" == "Synced" ]; then
    echo -e "${YELLOW}⚠ Phoenix synced but not yet healthy${NC}"
    echo "   Run: kubectl get pods -n cortex-knowledge -l app=phoenix"
    echo "   Check logs: kubectl logs -n cortex-knowledge -l app=phoenix"
else
    echo -e "${YELLOW}⚠ Waiting for ArgoCD to sync${NC}"
    echo "   ArgoCD auto-syncs every 3 minutes"
    echo "   Force sync: kubectl patch application cortex-knowledge -n argocd --type merge -p '{\"metadata\":{\"annotations\":{\"argocd.argoproj.io/refresh\":\"hard\"}}}'"
fi

echo ""
echo "For detailed integration instructions, see:"
echo "  ~/Projects/cortex-gitops/apps/cortex-knowledge/PHOENIX-INTEGRATION.md"
echo ""
