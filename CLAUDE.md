# Claude Code Operational Directive
**Version**: 3.0.0 (Project Thunder)
**Date**: 2026-01-11
**Status**: ACTIVE

---

## Critical: Read This First

This directive defines how I (Claude Code) operate as the **Control Plane** for the Cortex infrastructure.

**IMPORTANT**: This file lives in `~/cortex-gitops` (this repository).
**All active development happens in TWO repositories**:
- `~/cortex-gitops` - Infrastructure changes (Kubernetes manifests) ⭐ YOU ARE HERE
- `~/cortex-platform` - Code changes (application source code)

---

## The Architecture

```
┌─────────────────────────────────────────────────┐
│          CONTROL PLANE (Local Machine)          │
│                                                  │
│  • Plans and designs                            │
│  • Writes manifests                             │
│  • Commits to Git                               │
│  • NEVER executes workloads                     │
│                                                  │
│  "The control plane whispers..."                │
└─────────────────────────────────────────────────┘
                     │
                     │ Git Push
                     ▼
┌─────────────────────────────────────────────────┐
│              GITHUB REPOSITORIES                 │
│                                                  │
│  cortex-gitops: Infrastructure manifests        │
│  cortex-platform: Application code              │
│                                                  │
│  Single source of truth                         │
└─────────────────────────────────────────────────┘
                     │
                     │ ArgoCD Watches
                     ▼
┌─────────────────────────────────────────────────┐
│               ARGOCD (in k3s)                    │
│                                                  │
│  • Polls GitHub every 3 minutes                 │
│  • Auto-syncs changes                           │
│  • Self-heals drift                             │
│  • Prunes deleted resources                     │
└─────────────────────────────────────────────────┘
                     │
                     │ Deploys
                     ▼
┌─────────────────────────────────────────────────┐
│           K3S CLUSTER (7 nodes)                  │
│                                                  │
│  • 120 resources managed by GitOps              │
│  • All workloads execute here                   │
│                                                  │
│  "...the cluster thunders."                     │
└─────────────────────────────────────────────────┘
```

---

## GitOps Workflow (THE ONLY WAY)

### When User Requests Infrastructure Changes

1. **I Think** (Control Plane Analysis)
   - Analyze the request
   - Plan the change
   - Decide what manifests need updating

2. **I Whisper to GitHub** (Modify Manifests)
   ```bash
   cd ~/cortex-gitops
   git pull origin main              # Always pull first (GitHub is source of truth)
   # Create/edit YAML manifests in apps/
   git add .
   git commit -m "Description of change"
   git push origin main
   # Optional: Delete local files after successful push
   # GitHub is the source of truth, local is just staging
   ```

3. **The Cluster Thunders** (ArgoCD Auto-Syncs)
   - ArgoCD detects change within 3 minutes
   - Automatically syncs to cluster
   - Self-heals any manual drift
   - I verify with: `kubectl get applications -n argocd`

### When User Requests Code Changes

1. **I Modify Code** (Platform Repository)
   ```bash
   cd ~/cortex-platform
   # Edit source files
   git add .
   git commit -m "Description of change"
   git push origin main
   ```

2. **CI/CD Builds** (Future - not yet implemented)
   - Build container images
   - Push to registry
   - Update cortex-gitops with new image tags

3. **ArgoCD Deploys** (Automatic)
   - Syncs new manifests
   - Pulls new images
   - Updates cluster

---

## Repository Structure

### cortex-gitops (Infrastructure) ⭐ PRIMARY WORK LOCATION
**Location**: `/Users/ryandahlberg/cortex-gitops` (or `~/cortex-gitops`)
**GitHub**: `https://github.com/ry-ops/cortex-gitops`
**Contains**: Kubernetes manifests only
**Usage**: ALL infrastructure changes happen here

```
cortex-gitops/
├── apps/
│   ├── cortex-system/     # 49 resources
│   ├── cortex/            # 16 resources
│   ├── cortex-chat/       # 17 resources
│   ├── cortex-dev/        # 8 resources
│   ├── cortex-cicd/       # 3 resources
│   ├── cortex-security/   # 12 resources
│   └── cortex-knowledge/  # 15 resources
├── argocd-apps/           # 7 Application definitions
└── README.md
```

**Total**: 121 YAML manifests

### cortex-platform (Application Code) ⭐ PRIMARY WORK LOCATION
**Location**: `/Users/ryandahlberg/cortex-platform` (or `~/cortex-platform`)
**GitHub**: `https://github.com/ry-ops/cortex-platform`
**Contains**: All application source code
**Usage**: ALL code changes happen here

```
cortex-platform/
├── services/
│   ├── mcp-servers/       # MCP server implementations
│   ├── api/               # API services
│   └── workers/           # Worker processes
├── lib/                   # Shared libraries
├── coordination/          # Agent coordination (5,471 files)
├── docs/                  # Documentation
├── testing/               # Test infrastructure
└── scripts/               # Build/deploy scripts
```

**Total**: 10,661 files

### cortex-k3s (Cluster Docs)
**Location**: `/Users/ryandahlberg/cortex-k3s` (separate repo, not nested)
**GitHub**: `https://github.com/ry-ops/cortex-k3s`
**Contains**: K3s cluster documentation
**Status**: Separate repository for cluster-specific docs

---

## Forbidden Operations

As the Control Plane, I **NEVER**:

❌ Run code locally (no `npm start`, `python app.py`, etc.)
❌ Build containers locally (no `docker build`)
❌ Deploy with kubectl directly (no `kubectl apply -f`)
❌ Start services locally (no local Redis, Postgres, etc.)
❌ Execute workloads on the control plane
❌ Make manual changes to the cluster

### Why?
- **Control plane whispers; cluster thunders**
- All execution happens on k3s, not locally
- All changes go through Git → ArgoCD → Cluster
- Manual changes would create drift (ArgoCD reverts them)

---

## Allowed Operations

As the Control Plane, I **DO**:

✅ Read files locally
✅ Modify manifests in `~/cortex-gitops`
✅ Modify code in `~/cortex-platform`
✅ Commit and push to GitHub
✅ Verify ArgoCD sync status
✅ Check cluster health with kubectl
✅ Read logs from cluster pods
✅ Plan and design solutions

---

## ArgoCD Applications

All 7 namespaces managed by ArgoCD:

| Application | Namespace | Resources | Status |
|-------------|-----------|-----------|--------|
| cortex-system | cortex-system | 49 | Synced |
| cortex-core | cortex | 16 | Synced |
| cortex-chat | cortex-chat | 17 | Synced |
| cortex-dev | cortex-dev | 8 | Synced |
| cortex-cicd | cortex-cicd | 3 | Synced |
| cortex-security | cortex-security | 12 | Synced |
| cortex-knowledge | cortex-knowledge | 15 | Synced |

**Total**: 120 resources under GitOps control

### ArgoCD Settings
- **Auto-sync**: Enabled (checks every 3 minutes)
- **Self-heal**: Enabled (reverts manual changes)
- **Prune**: Enabled (deletes removed resources)

---

## Common Tasks

### Add a New Service

1. Write Kubernetes manifests
2. Save to `~/cortex-gitops/apps/<namespace>/`
3. Commit and push
4. ArgoCD auto-syncs within 3 minutes

### Update Existing Service

1. Edit manifest in `~/cortex-gitops/apps/<namespace>/`
2. Commit and push
3. ArgoCD auto-syncs

### Change Application Code

1. Edit code in `~/cortex-platform/`
2. Commit and push
3. (Future: CI/CD builds new image)
4. Update image tag in cortex-gitops
5. ArgoCD deploys new version

### Rollback a Change

```bash
cd ~/cortex-gitops
git log --oneline  # Find commit to revert
git revert <commit-hash>
git push origin main
# ArgoCD auto-syncs the rollback
```

### Check Sync Status

```bash
kubectl get applications -n argocd
kubectl get pods -n <namespace>
```

---

## Verification Commands

### GitOps Health
```bash
# Check ArgoCD applications
kubectl get applications -n argocd

# Check specific app details
kubectl describe application cortex-system -n argocd

# Force sync if needed (rare)
kubectl patch application cortex-system -n argocd \
  --type merge -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
```

### Cluster Health
```bash
# Check pods
kubectl get pods -A

# Check specific namespace
kubectl get all -n cortex-system

# Check logs
kubectl logs -n <namespace> <pod-name>
```

### Repository Status
```bash
# Check cortex-gitops
cd ~/cortex-gitops && git status

# Check cortex-platform
cd ~/cortex-platform && git status
```

---

## Migration History (Project Thunder)

**Date**: 2026-01-11
**Duration**: ~90 minutes
**Status**: Complete

### What Was Migrated
- **From**: 17,024 files in `/projects/cortex`
- **To**: 121 manifests in cortex-gitops + 10,661 files in cortex-platform
- **Reduction**: 81.3% local file reduction

### Before Project Thunder
- 6,247 files scattered across local machine
- 73+ deployed resources with no source of truth
- All deployments via manual `kubectl apply`
- Zero ArgoCD applications configured
- 100% cluster drift
- No audit trail

### After Project Thunder
- 120 resources under GitOps control
- 7 ArgoCD applications (100% synced)
- Auto-sync, self-heal, prune all enabled
- Single source of truth in Git
- Full audit trail via Git history
- Zero manual deployments

### Cleanup
- Deleted 13,699+ duplicate files from `/projects/cortex`
- Moved `cortex-k3s/` to `~/cortex-k3s` (separate repo)
- Kept only: .git/, .claude/, .github/, .githooks/, cortex-readme.png, .gitignore

---

## Reference Documentation

**Desktop Files** (created during Project Thunder):
- `from-chaos-to-gitops.md` - Complete migration story
- `PROJECT-THUNDER-COMPLETE.md` - Migration results
- `CORTEX-CLEANUP-COMPLETE.md` - Cleanup summary

**Session Transcript**:
- `/Users/ryandahlberg/.claude/projects/-Users-ryandahlberg-Projects-cortex/2e549f3c-cce5-4eb2-86bd-069fa8fefe46.jsonl`

---

## Quick Reference

| Task | Command | Location |
|------|---------|----------|
| Infrastructure change | Edit YAML, commit, push | `~/cortex-gitops` |
| Code change | Edit code, commit, push | `~/cortex-platform` |
| Check ArgoCD | `kubectl get applications -n argocd` | Any terminal |
| Check pods | `kubectl get pods -A` | Any terminal |
| Rollback | `git revert <hash>` then push | `~/cortex-gitops` |
| View logs | `kubectl logs -n <ns> <pod>` | Any terminal |

---

## Philosophy

> **"The control plane whispers; the cluster thunders."**

- Control plane (local machine): Plans, writes, commits to Git
- Data plane (k3s cluster): Executes workloads, enforces state
- Git: Single source of truth between them
- ArgoCD: Enforcement mechanism (pull-based)

**Never break this separation.**

---

## Version History

- **v3.0.0** (2026-01-11): Project Thunder - Full GitOps migration
- **v2.1.0** (2025-12-XX): Pre-GitOps control plane directive
- **v1.0.0** (2025-11-XX): Initial directive

---

**This is the way.** ⚡
