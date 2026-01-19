# Cortex Operational Principles

**Version**: 1.0.0
**Date**: 2026-01-16
**Status**: MANDATORY

---

## ⚠️ CRITICAL: No Quick Fixes

### The Rule

**When something doesn't work: STOP. ROLLBACK. RETHINK.**

**NEVER** do iterative "quick fixes" trying different solutions in rapid succession.

### Why This Matters

Quick fixes create:
- ❌ Technical debt
- ❌ Unclear root cause analysis
- ❌ Band-aid solutions that mask deeper issues
- ❌ Untested changes rushed to production
- ❌ Poor documentation of what actually fixed the problem
- ❌ Difficulty reproducing or understanding the solution later

### The Correct Approach

1. **STOP** - When you hit an error, stop immediately
2. **ANALYZE** - Consult debugging playbooks: `docs/playbooks/INDEX.md`
3. **DESIGN** - Plan a proper solution (use EnterPlanMode if needed)
4. **ROLLBACK** - Revert any failed attempts via Git
5. **IMPLEMENT** - Apply the designed solution once
6. **VERIFY** - Confirm it works
7. **DOCUMENT** - Explain what was wrong and why the fix works

### When to Consult Playbooks

Before attempting any fix, check if a debugging playbook exists:

- **Pod Issues**: [`docs/playbooks/pod-debugging/`](../playbooks/pod-debugging/)
  - ImagePullBackOff → [image-pull-failures.md](../playbooks/pod-debugging/image-pull-failures.md)
  - CrashLoopBackOff → [crashloop-backoff.md](../playbooks/pod-debugging/crashloop-backoff.md)

- **Network Issues**: [`docs/playbooks/network/`](../playbooks/network/)
  - LoadBalancer unreachable from VPN → [metallb-l2-vpn-issues.md](../playbooks/network/metallb-l2-vpn-issues.md)
  - Service connectivity → [service-connectivity.md](../playbooks/network/service-connectivity.md)

- **Resource Issues**: [`docs/playbooks/resources/`](../playbooks/resources/)
  - Pod creation forbidden → [limitrange-violations.md](../playbooks/resources/limitrange-violations.md)
  - OOMKilled → [oom-killed.md](../playbooks/resources/oom-killed.md)

- **GitOps Issues**: [`docs/playbooks/gitops/`](../playbooks/gitops/)
  - ArgoCD OutOfSync → [argocd-sync-failures.md](../playbooks/gitops/argocd-sync-failures.md)
  - Build job timeout → [kaniko-build-timeouts.md](../playbooks/gitops/kaniko-build-timeouts.md)

**Full index**: [`docs/playbooks/INDEX.md`](../playbooks/INDEX.md)

### Example: What NOT to Do (What I Did Today)

**BAD APPROACH** (improvement-detector pip permissions):
1. Try `--user` flag → Commit → Push → Test → Failed
2. Try `HOME=/tmp` → Commit → Push → Test → Failed
3. Try `PYTHONUSERBASE=/tmp/.local` → Commit → Push → Test → Worked

**Result**: 3 commits, 3 deployments, unclear which fix actually solved it

**GOOD APPROACH** (What I should have done):
1. **STOP** - First pip permission error
2. **ANALYZE** - Research: non-root user needs writable home for pip --user
3. **DESIGN** - Solution: Set HOME and PYTHONUSERBASE to writable location (/tmp)
4. **IMPLEMENT** - One commit with both env vars
5. **VERIFY** - Test the single change
6. **DOCUMENT** - "pip --user requires HOME and PYTHONUSERBASE to be writable; security context runs as non-root user 1000; /tmp is writable via emptyDir volume mount"

**Result**: 1 commit, 1 deployment, clear understanding of root cause and solution

---

## 🚫 No Local Development

### The Rule

**ALL development happens in the cluster via GitOps.**

**NEVER** run code locally unless explicitly instructed by the user.

### What This Means

❌ **NO** local `docker build`
❌ **NO** local `npm start` / `python app.py` / etc.
❌ **NO** local `kubectl apply -f` (GitOps only)
❌ **NO** local Redis, Postgres, or service testing
❌ **NO** "let me test this locally first"

✅ **YES** - Write manifests in `~/Projects/cortex-gitops`
✅ **YES** - Commit to Git
✅ **YES** - Push to GitHub
✅ **YES** - Let ArgoCD deploy to cluster
✅ **YES** - Verify in cluster with kubectl/logs
✅ **YES** - Rollback via Git if it fails

### Why This Matters

**"The control plane whispers; the cluster thunders."**

- Local environment ≠ Cluster environment
- What works locally may fail in cluster (and vice versa)
- GitOps requires Git as single source of truth
- Local testing breaks the GitOps flow
- All execution happens on k3s, not locally

### The Only Exception

**User explicitly says**: "test this locally first" or "run this on your machine"

Otherwise: **Always deploy to cluster via GitOps.**

---

## 🛑 Stop and Ask

### When to STOP and Ask User

If you encounter infrastructure that **requires** local development or quick fixes:

1. **STOP immediately**
2. **Don't try to work around it**
3. **Document the issue**
4. **Ask the user** how they want to proceed

### Red Flags (Stop and Ask)

- "I need to build this container locally to test"
- "Let me try a few different configurations to see what works"
- "This needs a local database to develop against"
- "I'll iterate on this until it works"
- "Let me test this approach... if it doesn't work I'll try another"

### Correct Response

```
STOP. I've identified that [component] requires [local development / quick fixes].

Issue: [Clear description]
Root Cause: [Analysis]
Options:
1. [Proper solution A]
2. [Proper solution B]

How would you like me to proceed?
```

---

## 📋 Checklist: Before Making a Change

Before committing **any** change, verify:

- [ ] I understand the **root cause** (not just symptoms)
- [ ] I have a **designed solution** (not trial and error)
- [ ] This is **one coherent change** (not "let me try this")
- [ ] I can **explain why this fixes it** (not "hopefully this works")
- [ ] This follows **GitOps workflow** (Git → ArgoCD → Cluster)
- [ ] I am **not doing local development** (unless explicitly told)
- [ ] If this fails, I will **rollback and rethink** (not iterate)

---

## 🔄 Rollback Procedure

If a change doesn't work:

```bash
# 1. STOP - Don't try another quick fix

# 2. ROLLBACK via Git
cd ~/Projects/cortex-gitops
git log --oneline -5  # Find last known good commit
git revert <bad-commit-hash>
git push origin main
# ArgoCD auto-syncs the rollback within 3 minutes

# 3. ANALYZE - Understand what went wrong
# Read logs, research, understand root cause

# 4. DESIGN - Plan proper solution
# Use EnterPlanMode for complex changes
# Document the approach before implementing

# 5. IMPLEMENT - One well-designed change
# Not multiple trial-and-error attempts
```

---

## 📚 Examples of Good vs Bad

### Example 1: Resource Limits

**BAD** (What I did):
- Commit 1: Try 200m CPU → Doesn't work
- Commit 2: Try 125m CPU → Works

**GOOD** (What I should have done):
- STOP at first error
- READ the LimitRange error: "max ratio is 4"
- CALCULATE: 500m limit / 4 = 125m minimum request
- Commit once with correct value

### Example 2: Docker Registry Issues

**BAD**:
- Try Docker Hub → TLS fails
- Try different image tag → Fails
- Try local registry → Works

**GOOD**:
- STOP at TLS failure
- ANALYZE: Workers can't reach Docker Hub
- DESIGN: Use local registry for all images
- Document: "Cluster has Docker Hub TLS issues, use 10.43.170.72:5000"
- Implement once with local registry

### Example 3: Environment Variables

**BAD** (What I did today):
- Commit 1: Add --user flag
- Commit 2: Set HOME=/tmp
- Commit 3: Set PYTHONUSERBASE=/tmp/.local
- Final: Worked (but which one actually fixed it?)

**GOOD** (What I should have done):
- STOP at first pip permission error
- RESEARCH: pip --user documentation
- UNDERSTAND: Needs both HOME and PYTHONUSERBASE writable
- IMPLEMENT: One commit with both env vars
- CLEAR: "pip --user writes to $PYTHONUSERBASE/.local, default is /root which is read-only for user 1000"

---

## 🎯 Success Criteria

You're following this principle when:

✅ Each commit has a **clear, single purpose**
✅ You can **explain the root cause** of every issue
✅ You **stop and ask** rather than iterate blindly
✅ Changes are **designed before implemented**
✅ Rollbacks happen **immediately** when something fails
✅ All development happens **in cluster via GitOps**
✅ You **never run code locally** (unless explicitly told)

You're violating this principle when:

❌ Multiple commits trying different solutions
❌ "Let me try this..." without understanding why
❌ Iterating through options hoping one works
❌ Running code locally to "test quickly"
❌ Building containers on local machine
❌ Skipping root cause analysis to "just fix it"

---

## 📖 Related Documentation

- **CLAUDE.md** - GitOps workflow and control plane principles
- **from-chaos-to-gitops.md** - Why GitOps exists (to prevent chaos)
- **PROJECT-THUNDER-COMPLETE.md** - Migration to proper GitOps workflow

---

## ✅ Acknowledgment

**I (Claude Code) acknowledge**:

1. ✅ **No quick fixes** - Stop, rollback, rethink
2. ✅ **No local development** - GitOps only (unless explicitly instructed)
3. ✅ **Stop and ask** - If infrastructure requires local dev
4. ✅ **Root cause analysis** - Understand before implementing
5. ✅ **Designed solutions** - Plan before coding
6. ✅ **Rollback immediately** - Don't iterate on failures

**Violation of these principles is unacceptable.**

---

**Approved By**: User (2026-01-16)
**Effective Immediately**
**No Exceptions Without Explicit User Permission**
