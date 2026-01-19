# Debugging Playbooks Index
**Last Updated**: 2026-01-18
**Version**: 1.0.0

---

## Overview

This directory contains systematic debugging playbooks for the Cortex platform. Each playbook provides source-grounded troubleshooting procedures, following the **context-first debugging model** from GitHub Copilot Spaces.

### Philosophy

> **"STOP. ANALYZE. DESIGN. IMPLEMENT."**

Playbooks help you:
1. **STOP** - Recognize the issue quickly via symptoms
2. **ANALYZE** - Follow systematic investigation steps with source citations
3. **DESIGN** - Choose the right solution from documented root causes
4. **IMPLEMENT** - Apply fixes with verification steps

### How to Use

1. **Find your symptom** in the [Quick Reference Matrix](#quick-reference-matrix) below
2. **Open the relevant playbook** and follow investigation steps
3. **Cite sources** - All commands reference specific files/lines
4. **Document findings** - Add real examples to playbooks after resolution

---

## Playbook Categories

### 🔴 Pod Debugging
Issues with pod startup, crashes, and container problems.

| Playbook | Symptoms | Severity |
|----------|----------|----------|
| [Image Pull Failures](./pod-debugging/image-pull-failures.md) | ImagePullBackOff, ErrImagePull, registry timeouts | High |
| [CrashLoop BackOff](./pod-debugging/crashloop-backoff.md) | Pod restarts repeatedly, OOMKilled, exit code errors | High |

### 🟠 Network Issues
Service connectivity, ingress, and network policy problems.

| Playbook | Symptoms | Severity |
|----------|----------|----------|
| [MetalLB L2 VPN Issues](./network/metallb-l2-vpn-issues.md) | LoadBalancer IPs unreachable over VPN, ARP failures | Medium |
| [Service Connectivity](./network/service-connectivity.md) | Services unreachable, DNS resolution failures | High |

### 🟡 Resource Issues
Resource limits, quotas, and scheduling problems.

| Playbook | Symptoms | Severity |
|----------|----------|----------|
| [LimitRange Violations](./resources/limitrange-violations.md) | Pod creation forbidden, ratio violations | Medium |
| [OOM Killed](./resources/oom-killed.md) | Out of memory errors, pods killed | High |

### 🟢 GitOps Issues
ArgoCD, manifests, and deployment pipeline problems.

| Playbook | Symptoms | Severity |
|----------|----------|----------|
| [ArgoCD Sync Failures](./gitops/argocd-sync-failures.md) | OutOfSync status, ComparisonError, drift | High |
| [Kaniko Build Timeouts](./gitops/kaniko-build-timeouts.md) | Build job failures, registry timeouts | High |

---

## Quick Reference Matrix

### By Error Message

| Error Message | Playbook |
|---------------|----------|
| `ImagePullBackOff` | [Image Pull Failures](./pod-debugging/image-pull-failures.md) |
| `ErrImagePull` | [Image Pull Failures](./pod-debugging/image-pull-failures.md) |
| `CrashLoopBackOff` | [CrashLoop BackOff](./pod-debugging/crashloop-backoff.md) |
| `OOMKilled` | [OOM Killed](./resources/oom-killed.md) |
| `forbidden: memory/cpu max limit to request ratio` | [LimitRange Violations](./resources/limitrange-violations.md) |
| `dial tcp 10.43.170.72:5000: i/o timeout` | [Kaniko Build Timeouts](./gitops/kaniko-build-timeouts.md) |
| `OutOfSync` (ArgoCD) | [ArgoCD Sync Failures](./gitops/argocd-sync-failures.md) |
| `ComparisonError` (ArgoCD) | [ArgoCD Sync Failures](./gitops/argocd-sync-failures.md) |
| `remote error: tls: handshake failure` | [Image Pull Failures](./pod-debugging/image-pull-failures.md) |
| `error converting YAML to JSON` | [ArgoCD Sync Failures](./gitops/argocd-sync-failures.md) |

### By Symptom

| Symptom | Playbook |
|---------|----------|
| Pod won't start | [Image Pull Failures](./pod-debugging/image-pull-failures.md) |
| Pod keeps restarting | [CrashLoop BackOff](./pod-debugging/crashloop-backoff.md) |
| Service unreachable from VPN | [MetalLB L2 VPN Issues](./network/metallb-l2-vpn-issues.md) |
| Service unreachable from cluster | [Service Connectivity](./network/service-connectivity.md) |
| Git changes not deploying | [ArgoCD Sync Failures](./gitops/argocd-sync-failures.md) |
| Build job hanging | [Kaniko Build Timeouts](./gitops/kaniko-build-timeouts.md) |
| Image not in registry | [Kaniko Build Timeouts](./gitops/kaniko-build-timeouts.md) |
| Pod creation forbidden | [LimitRange Violations](./resources/limitrange-violations.md) |
| LoadBalancer IP not pinging | [MetalLB L2 VPN Issues](./network/metallb-l2-vpn-issues.md) |

### By Component

| Component | Common Issues | Playbooks |
|-----------|---------------|-----------|
| ArgoCD | Sync failures, drift, YAML errors | [ArgoCD Sync Failures](./gitops/argocd-sync-failures.md) |
| MetalLB | L2 mode over VPN, LoadBalancer unreachable | [MetalLB L2 VPN Issues](./network/metallb-l2-vpn-issues.md) |
| Kaniko | Build timeouts, registry push failures | [Kaniko Build Timeouts](./gitops/kaniko-build-timeouts.md) |
| Docker Registry | Connectivity timeout, image pull failures | [Image Pull Failures](./pod-debugging/image-pull-failures.md), [Kaniko Build Timeouts](./gitops/kaniko-build-timeouts.md) |
| Pods | Won't start, crashing, OOM | [Image Pull Failures](./pod-debugging/image-pull-failures.md), [CrashLoop BackOff](./pod-debugging/crashloop-backoff.md), [OOM Killed](./resources/oom-killed.md) |
| Services | Unreachable, DNS issues | [Service Connectivity](./network/service-connectivity.md), [MetalLB L2 VPN Issues](./network/metallb-l2-vpn-issues.md) |
| LimitRange | Pod creation forbidden | [LimitRange Violations](./resources/limitrange-violations.md) |

---

## Workflow Integration

### Standard Debugging Workflow

```
┌──────────────────────────────────────────────┐
│ 1. Observe Symptom                           │
│    (Pod not starting, service unreachable)   │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│ 2. STOP - Consult Playbook Index             │
│    Find matching symptom/error               │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│ 3. ANALYZE - Follow Playbook Steps           │
│    - Run diagnostic commands                 │
│    - Check file citations                    │
│    - Identify root cause                     │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│ 4. DESIGN - Choose Solution                  │
│    - Review root cause options               │
│    - Select appropriate fix                  │
│    - Plan verification steps                 │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│ 5. IMPLEMENT - Apply Fix via GitOps          │
│    - Edit manifests in cortex-gitops         │
│    - Commit with descriptive message         │
│    - Push to GitHub → ArgoCD syncs           │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│ 6. VERIFY - Confirm Resolution               │
│    - Run verification commands               │
│    - Check pod/service status                │
│    - Test functionality                      │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│ 7. DOCUMENT - Update Playbook                │
│    - Add real example with commit hash       │
│    - Document any new root causes            │
│    - Improve investigation steps             │
└──────────────────────────────────────────────┘
```

### Integration with Existing Docs

**Before debugging**:
- Read [OPERATIONAL-PRINCIPLES.md](../OPERATIONAL-PRINCIPLES.md) - No quick fixes mandate
- Review [CLAUDE.md](../CLAUDE.md) - GitOps workflow requirements

**During debugging**:
- Consult relevant playbook from this index
- Follow source-grounded investigation steps
- Document findings in commit messages

**After resolution**:
- Update playbook with real example
- Add commit hash and resolution details
- Improve playbook if new root cause discovered

---

## Contributing to Playbooks

### When to Add a New Playbook

- Encountered an issue 3+ times
- Issue took >30 minutes to debug
- Solution required multiple files/steps
- Pattern likely to recur

### How to Create a Playbook

1. Copy [TEMPLATE.md](./TEMPLATE.md)
2. Fill in all sections with source citations
3. Include real examples with commit hashes
4. Add to appropriate category directory
5. Update this INDEX.md with new playbook

### Playbook Quality Standards

✅ **Source-Grounded**:
- File paths with line numbers: `apps/namespace/file.yaml:123`
- Kubectl commands with expected output
- Commit hashes for real examples

✅ **Actionable**:
- Clear investigation steps
- Step-by-step solutions
- Verification commands

✅ **Consistent**:
- Follows TEMPLATE.md structure
- Matches existing doc style
- Uses standard terminology

✅ **Validated**:
- Based on real debugging sessions
- Solutions proven to work
- Examples cite actual commits

---

## Related Documentation

### Operational Guidelines
- [CLAUDE.md](../CLAUDE.md) - Control plane directive and GitOps workflow
- [OPERATIONAL-PRINCIPLES.md](../OPERATIONAL-PRINCIPLES.md) - No quick fixes, no local dev
- [CORTEX-SYSTEM-STATUS.md](../CORTEX-SYSTEM-STATUS.md) - Current system health
- [CORTEX-VISUAL-FLOW.md](../CORTEX-VISUAL-FLOW.md) - Architecture overview

### Component Documentation
- [CORTEX-EVERYTHING-BAGEL.md](../CORTEX-EVERYTHING-BAGEL.md) - Component inventory
- [CORTEX-ROLES-RESPONSIBILITIES.md](../CORTEX-ROLES-RESPONSIBILITIES.md) - Role definitions
- [vulnerability-remediation-workflow.md](../vulnerability-remediation-workflow.md) - Security workflow

### Specific Workflows
- [MANUAL_STEPS_REQUIRED.md](../MANUAL_STEPS_REQUIRED.md) - Manual procedures
- [github-security-mcp-deployment.md](../github-security-mcp-deployment.md) - Security MCP setup

---

## Playbook Statistics

**Total Playbooks**: 6 (5 core + 1 template)
**Categories**: 4 (Pod, Network, Resources, GitOps)
**Real Examples Documented**: 8+
**Commit References**: 4+
**Last Updated**: 2026-01-18

---

## Feedback and Improvements

Playbooks are living documents. After each debugging session:

1. **Did the playbook help?** - Add your experience to "Real Examples"
2. **Found a new root cause?** - Add it to "Common Root Causes"
3. **Better investigation step?** - Update "Investigation Steps"
4. **Playbook missing?** - Create new one using TEMPLATE.md

**Philosophy**: Each debugging session should make the next one faster.

---

**Version History**:
- v1.0.0 (2026-01-18) - Initial release with 5 core playbooks
