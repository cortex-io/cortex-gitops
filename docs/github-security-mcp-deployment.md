# GitHub Security MCP Server - Deployment Guide

Complete deployment instructions for the GitHub vulnerability remediation system.

## Overview

The GitHub Security MCP Server enables chat-driven vulnerability detection and remediation across all `ry-ops` organization repositories. This guide covers the complete deployment process.

## Components Created

### 1. MCP Server Implementation
**Location**: `/Users/ryandahlberg/Projects/cortex-platform/services/mcp-servers/github-security/`

```
github-security/
├── src/
│   └── mcp_github_security/
│       ├── __init__.py          # Package initialization
│       └── server.py            # Main MCP server (590 lines)
├── pyproject.toml               # Python package configuration
└── README.md                    # Server documentation
```

**Tools Implemented** (8 total):
1. `list_vulnerabilities` - Organization-wide scan
2. `list_repo_vulnerabilities` - Repository-specific scan
3. `get_vulnerability_details` - Detailed CVE information
4. `get_vulnerable_files` - List affected manifest files
5. `get_remediation_pr` - Check for Dependabot fix PRs
6. `dismiss_vulnerability` - Dismiss false positives
7. `list_org_repositories` - List all org repositories
8. `get_vulnerability_stats` - Organization statistics

### 2. Kubernetes Manifests
**Location**: `/Users/ryandahlberg/Projects/cortex-gitops/apps/cortex-system/`

- `github-security-mcp-server-deployment.yaml` - Deployment with HTTP wrapper
- `github-security-mcp-server-service.yaml` - ClusterIP service on port 3003

### 3. MoE Router Integration
**Location**: `/Users/ryandahlberg/Projects/cortex-platform/services/mcp-servers/cortex/src/moe-router.js`

Added `github_security` route with 18 keywords (priority 100).

### 4. Documentation
**Location**: `/Users/ryandahlberg/Projects/cortex-gitops/docs/`

- `vulnerability-remediation-workflow.md` - Complete workflow guide (500+ lines)
- `github-security-mcp-deployment.md` - This deployment guide

---

## Prerequisites

### 1. GitHub Personal Access Token

Create a token with the following scopes:

**Required Scopes**:
- `security_events` - Read/write security events (Dependabot alerts)
- `repo` - Full repository access (required for private repos)

**Steps**:
1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Set name: `cortex-github-security-mcp`
4. Select scopes: `security_events`, `repo`
5. Click "Generate token"
6. **Save the token securely** - you'll need it in the next step

### 2. Kubernetes Cluster Access

Ensure you have access to the k3s cluster:
```bash
kubectl get nodes
kubectl get namespaces | grep cortex-system
```

### 3. Required ConfigMaps

The MCP HTTP wrapper ConfigMap should already exist:
```bash
kubectl get configmap mcp-http-wrapper -n cortex-system
```

---

## Deployment Steps

### Step 1: Create Source Code ConfigMaps

The deployment references ConfigMaps for the Python source code. Create them:

```bash
cd ~/Projects/cortex-platform/services/mcp-servers/github-security

# Create server.py ConfigMap
kubectl create configmap github-security-mcp-server-py \
  --from-file=server.py=src/mcp_github_security/server.py \
  -n cortex-system \
  --dry-run=client -o yaml | kubectl apply -f -

# Create __init__.py ConfigMap
kubectl create configmap github-security-mcp-init-py \
  --from-file=__init__.py=src/mcp_github_security/__init__.py \
  -n cortex-system \
  --dry-run=client -o yaml | kubectl apply -f -
```

**Verify**:
```bash
kubectl get configmap -n cortex-system | grep github-security
```

Expected output:
```
github-security-mcp-init-py     1      30s
github-security-mcp-server-py   1      30s
```

### Step 2: Update Deployment with GitHub Token

Edit the deployment manifest to add your GitHub token:

```bash
cd ~/Projects/cortex-gitops/apps/cortex-system

# Option 1: Edit directly
vim github-security-mcp-server-deployment.yaml
# Find GITHUB_TOKEN and replace "REQUIRES_MANUAL_SETUP" with your token

# Option 2: Use sed (replace YOUR_TOKEN_HERE)
sed -i '' 's/REQUIRES_MANUAL_SETUP/ghp_YOUR_TOKEN_HERE/g' \
  github-security-mcp-server-deployment.yaml
```

**Security Note**: For production, use Kubernetes Secrets instead of plain text:
```bash
kubectl create secret generic github-security-token \
  --from-literal=token=ghp_YOUR_TOKEN_HERE \
  -n cortex-system
```

Then update the deployment to reference the secret:
```yaml
env:
- name: GITHUB_TOKEN
  valueFrom:
    secretKeyRef:
      name: github-security-token
      key: token
```

### Step 3: Commit and Push to GitOps Repository

Following the GitOps workflow:

```bash
cd ~/Projects/cortex-gitops

# Check git status
git status

# Add the new manifests and documentation
git add apps/cortex-system/github-security-mcp-server-deployment.yaml
git add apps/cortex-system/github-security-mcp-server-service.yaml
git add docs/github-security-mcp-deployment.md
git add docs/vulnerability-remediation-workflow.md

# Commit
git commit -m "$(cat <<'EOF'
Add GitHub Security MCP Server for vulnerability remediation

Added comprehensive vulnerability detection and remediation system:

Infrastructure:
- GitHub Security MCP Server deployment (port 3003)
- Service definition for cluster access
- ConfigMap references for source code

Features:
- Organization-wide vulnerability scanning
- Repository-specific vulnerability queries
- Detailed CVE analysis with CVSS scores
- Dependabot PR detection and tracking
- Alert dismissal for false positives
- Vulnerability statistics and reporting

Integration:
- MoE router integration with 18 security keywords
- Automatic routing of vulnerability queries
- Priority 100 (highest) for security concerns

Documentation:
- Complete deployment guide
- Vulnerability remediation workflow
- Best practices and troubleshooting

Enables chat-driven vulnerability management across all ry-ops repositories.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"

# Push to GitHub
git push origin main
```

### Step 4: Commit MoE Router Changes

The MoE router was also updated in the cortex-platform repository:

```bash
cd ~/Projects/cortex-platform

# Check git status
git status

# Add the router changes
git add services/mcp-servers/cortex/src/moe-router.js

# Commit
git commit -m "$(cat <<'EOF'
Add GitHub Security routing to MoE router

Added github_security route with priority 100 for vulnerability queries:
- 18 keywords covering CVE, Dependabot, dependency management
- Automatic routing of security-related queries
- Reduced Sandfly priority to 90 to avoid keyword conflicts

Keywords: vulnerability, cve, dependabot, security alert, dependency,
upgrade, patch, remediation, npm audit, pip-audit, etc.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"

# Push to GitHub
git push origin main
```

### Step 5: Wait for ArgoCD Auto-Sync

ArgoCD will detect the changes and auto-sync within 3 minutes.

**Monitor sync progress**:
```bash
# Watch ArgoCD applications
watch kubectl get applications -n argocd

# Check cortex-system sync status
kubectl get application cortex-system -n argocd -o yaml | grep -A 5 status
```

### Step 6: Verify Deployment

Check that the GitHub Security MCP server is running:

```bash
# Check pod status
kubectl get pods -n cortex-system | grep github-security

# Expected output:
# github-security-mcp-server-xxxxxxxxx-xxxxx   1/1     Running   0          2m

# Check service
kubectl get service github-security-mcp-server -n cortex-system

# Check logs
kubectl logs -n cortex-system -l app=github-security-mcp-server --tail=50

# Test health endpoint
kubectl port-forward -n cortex-system service/github-security-mcp-server 3003:3003 &
curl http://localhost:3003/health
# Expected: {"status": "healthy"}
```

### Step 7: Test via Chat Interface

Once deployed, test the integration:

**Test 1: Organization scan**
```
User: "Show me vulnerability statistics"
Expected: Server responds with vulnerability breakdown
```

**Test 2: Specific repository**
```
User: "Show me vulnerabilities in DriveIQ"
Expected: List of vulnerabilities in the DriveIQ repository
```

**Test 3: Routing verification**
```
User: "Show me all critical CVEs"
Expected: MoE router directs to github_security system
```

---

## Configuration

### Environment Variables

The deployment uses these environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_TOKEN` | Required | GitHub Personal Access Token |
| `GITHUB_ORG` | `ry-ops` | GitHub organization name |
| `GITHUB_API_URL` | `https://api.github.com` | GitHub API base URL |
| `GITHUB_TIMEOUT` | `30` | Request timeout (seconds) |
| `MCP_COMMAND` | `python -m mcp_github_security.server` | MCP server command |
| `PORT` | `3003` | HTTP server port |

### Resource Limits

Default resource allocation:

```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 400m
    memory: 256Mi
```

Adjust if needed based on usage patterns.

---

## Troubleshooting

### Pod Not Starting

**Check pod events**:
```bash
kubectl describe pod -n cortex-system -l app=github-security-mcp-server
```

**Common issues**:
1. ConfigMaps missing: Run Step 1 again
2. Image pull errors: Check network connectivity
3. Init container failing: Check volume mounts

### ConfigMap Not Found

```bash
# Verify ConfigMaps exist
kubectl get configmap -n cortex-system | grep github-security

# Recreate if missing (see Step 1)
```

### Authentication Errors

```bash
# Check logs for auth errors
kubectl logs -n cortex-system -l app=github-security-mcp-server | grep -i auth

# Verify token has correct scopes at:
# https://github.com/settings/tokens
```

### API Rate Limiting

GitHub allows 5,000 requests/hour for authenticated users.

**Check rate limit status**:
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://api.github.com/rate_limit
```

**Mitigation**:
- Reduce query frequency
- Implement caching (future enhancement)
- Use conditional requests with ETags

### Server Not Responding

```bash
# Check readiness probe
kubectl get pods -n cortex-system -l app=github-security-mcp-server -o wide

# Check service endpoints
kubectl get endpoints github-security-mcp-server -n cortex-system

# Test directly
kubectl exec -it -n cortex-system deployment/github-security-mcp-server -- \
  curl http://localhost:3003/health
```

---

## Maintenance

### Updating the Server

When making changes to the server code:

1. **Update source files**:
```bash
cd ~/Projects/cortex-platform/services/mcp-servers/github-security
# Edit src/mcp_github_security/server.py
```

2. **Update ConfigMaps**:
```bash
kubectl create configmap github-security-mcp-server-py \
  --from-file=server.py=src/mcp_github_security/server.py \
  -n cortex-system \
  --dry-run=client -o yaml | kubectl apply -f -
```

3. **Restart deployment**:
```bash
kubectl rollout restart deployment github-security-mcp-server -n cortex-system
```

4. **Commit changes**:
```bash
cd ~/Projects/cortex-platform
git add services/mcp-servers/github-security/
git commit -m "Update GitHub Security MCP Server"
git push origin main
```

### Rotating GitHub Token

Every 90 days, rotate the GitHub token:

1. Generate new token at https://github.com/settings/tokens
2. Update the deployment or secret
3. Commit and push changes
4. ArgoCD will auto-sync

### Monitoring

**Key metrics to monitor**:
- Pod restarts: `kubectl get pods -n cortex-system -l app=github-security-mcp-server`
- Response times: Check logs for slow API calls
- Error rates: `kubectl logs -n cortex-system -l app=github-security-mcp-server | grep -i error`
- API rate limits: Monitor GitHub API usage

---

## Security Best Practices

### 1. Token Management
- ✅ Use Kubernetes Secrets (not environment variables)
- ✅ Rotate token every 90 days
- ✅ Use minimum required scopes
- ✅ Audit token usage regularly

### 2. Network Security
- ✅ Restrict egress to GitHub API only
- ✅ Use NetworkPolicy to limit pod access
- ✅ Enable TLS for all external connections

### 3. Access Control
- ✅ RBAC for deployment management
- ✅ Limit who can view/edit GitHub token
- ✅ Audit logs for all security operations

### 4. Data Privacy
- ✅ Server doesn't persist vulnerability data
- ✅ Sanitize sensitive data from logs
- ✅ Follow data retention policies

---

## Future Enhancements

### Phase 2: Automated Remediation
- Auto-create fix PRs from chat
- Batch vulnerability fixes
- CI/CD integration for testing fixes

### Phase 3: Proactive Monitoring
- GitHub webhooks for real-time alerts
- Scheduled vulnerability reports
- Slack/email notifications

### Phase 4: Advanced Analytics
- Vulnerability trend analysis
- SBOM (Software Bill of Materials) generation
- Custom policy enforcement
- Jira integration for tracking

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Cortex Chat Interface                    │
│  "Show me vulnerabilities in DriveIQ"                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                 MoE Router (cortex-mcp)                     │
│  Keywords: vulnerability, cve, dependabot, etc. (18 total)  │
│  Priority: 100 (highest)                                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│        GitHub Security MCP Server (port 3003)               │
│  Pod: github-security-mcp-server-xxx                        │
│  Service: github-security-mcp-server.cortex-system:3003     │
│  Tools: 8 (scan, analyze, remediate, dismiss, stats)        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   GitHub REST API                           │
│  Endpoint: https://api.github.com                           │
│  Auth: Bearer token (PAT with security_events + repo)       │
│  Rate Limit: 5,000 requests/hour                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Dependabot Alerts Database                     │
│  Organization: ry-ops                                       │
│  Repositories: All public and private repos                 │
│  Alert Types: Critical, High, Medium, Low                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Resource Summary

### Files Created

**cortex-platform** (4 files):
```
services/mcp-servers/github-security/
├── src/mcp_github_security/
│   ├── __init__.py (3 lines)
│   └── server.py (590 lines)
├── pyproject.toml (18 lines)
└── README.md (250 lines)

services/mcp-servers/cortex/src/
└── moe-router.js (updated)
```

**cortex-gitops** (4 files):
```
apps/cortex-system/
├── github-security-mcp-server-deployment.yaml (126 lines)
└── github-security-mcp-server-service.yaml (17 lines)

docs/
├── vulnerability-remediation-workflow.md (500+ lines)
└── github-security-mcp-deployment.md (this file)
```

### Kubernetes Resources

| Resource | Namespace | Replicas | Port |
|----------|-----------|----------|------|
| Deployment | cortex-system | 1 | 3003 |
| Service | cortex-system | - | 3003 |
| ConfigMap (server.py) | cortex-system | - | - |
| ConfigMap (__init__.py) | cortex-system | - | - |

---

## Support

### Getting Help

1. **Server Logs**: `kubectl logs -n cortex-system -l app=github-security-mcp-server`
2. **GitHub API Status**: https://www.githubstatus.com/
3. **Server README**: `~/Projects/cortex-platform/services/mcp-servers/github-security/README.md`
4. **Workflow Guide**: `~/Projects/cortex-gitops/docs/vulnerability-remediation-workflow.md`

### Common Questions

**Q: Can I scan private repositories?**
A: Yes, if your GitHub token has the `repo` scope.

**Q: How often should I scan for vulnerabilities?**
A: Weekly for proactive scanning, immediately for critical alerts.

**Q: What's the API rate limit?**
A: 5,000 requests/hour for authenticated users. Monitor usage via logs.

**Q: Can I auto-fix vulnerabilities?**
A: Currently manual via Dependabot PRs. Auto-fix is a future enhancement.

**Q: How do I add more repositories?**
A: All ry-ops repositories are automatically included.

---

## Changelog

### v1.0.0 (2026-01-12)
- Initial release
- 8 MCP tools for vulnerability management
- Organization-wide and repository-specific scanning
- CVE details with CVSS scores
- Dependabot PR detection
- Alert dismissal for false positives
- Vulnerability statistics and reporting
- MoE router integration
- Complete documentation

---

**Status**: Ready for deployment
**Last Updated**: 2026-01-12
**Maintained By**: Cortex Infrastructure Team
