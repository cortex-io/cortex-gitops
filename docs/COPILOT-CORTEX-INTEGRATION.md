# Copilot-Cortex Integration: AI Collaboration Loop

**Date**: 2026-01-15
**Status**: IMPLEMENTATION IN PROGRESS
**Pattern**: AI-to-AI Feedback Loop

---

## 🎯 Objective

Create a feedback loop where:
1. **Cortex (Claude)** writes code and pushes to GitHub
2. **GitHub Copilot** reviews the PR automatically
3. **Cortex** reads Copilot's suggestions via GitHub MCP
4. **Cortex** learns patterns and improves future code generation

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CORTEX (Claude Code)                      │
│  • Has live cluster context via MCP tools                   │
│  • Writes infrastructure code (K8s manifests, Python)       │
│  • Commits to cortex-gitops or cortex-platform              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Git Push
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    GITHUB REPOSITORY                         │
│  • cortex-gitops (infrastructure manifests)                 │
│  • cortex-platform (application code)                       │
│  • Branch protection: requires PR for main                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ PR Created
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  GITHUB COPILOT FOR PRS                      │
│  • Automatically reviews PR                                 │
│  • Checks: best practices, security, patterns              │
│  • Posts review comments with suggestions                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Review Comments Posted
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              GITHUB MCP SERVER (in K8s)                      │
│  • Polls GitHub API for new PR comments                     │
│  • Exposes via HTTP endpoint                                │
│  • Tool: list_pr_comments(repo, pr_number)                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ HTTP Request
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    CORTEX (Claude Code)                      │
│  • Reads Copilot's review comments                          │
│  • Analyzes suggestions:                                    │
│    - Valid? Apply to code                                   │
│    - Pattern? Remember for future                           │
│    - Context-specific? Explain why inapplicable            │
│  • Updates PR or documents reasoning                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 Implementation Phases

### Phase 1: Setup Prerequisites (CURRENT)

**Tasks**:
1. ✅ Verify GitHub token has PR read/write permissions
2. ⏳ Enable GitHub Copilot for Pull Requests on repos
3. ⏳ Deploy general GitHub MCP server (not just security)
4. ⏳ Configure branch protection to require PRs

**GitHub Token Permissions Needed**:
- `repo` (full control of private repositories)
- `pull_request` (read/write)
- `workflow` (update GitHub Actions)

**Repos to Enable**:
- `ry-ops/cortex-gitops`
- `ry-ops/cortex-platform`

---

### Phase 2: GitHub MCP Server Deployment

**Service**: `github-mcp-server` (general GitHub operations)

**Capabilities**:
- List repositories
- Create/read/update pull requests
- Read PR reviews and comments
- List commits and changes
- Manage issues

**Deployment**:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: github-mcp-server
  namespace: cortex-system
spec:
  type: ClusterIP
  ports:
  - port: 3002
    targetPort: 3002
    name: http
  selector:
    app: github-mcp-server
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: github-mcp-server
  namespace: cortex-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: github-mcp-server
  template:
    metadata:
      labels:
        app: github-mcp-server
    spec:
      containers:
      - name: mcp
        image: python:3.11-slim
        command:
        - /bin/bash
        - -c
        - |
          pip install mcp httpx PyGithub
          python /app/github-mcp-server.py
        env:
        - name: GITHUB_TOKEN
          valueFrom:
            secretKeyRef:
              name: github-token
              key: token
        - name: PORT
          value: "3002"
        ports:
        - containerPort: 3002
        volumeMounts:
        - name: app
          mountPath: /app
      volumes:
      - name: app
        configMap:
          name: github-mcp-server-code
```

**MCP Server Code** (`github-mcp-server.py`):
```python
#!/usr/bin/env python3
"""
GitHub MCP Server - General GitHub operations for Cortex
Provides tools for PR management, reviews, and collaboration with Copilot
"""
import os
import json
from typing import Any
from github import Github, GithubException
from mcp.server import Server
from mcp.types import Tool, TextContent

# Initialize GitHub client
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
gh = Github(GITHUB_TOKEN)

# Initialize MCP server
server = Server("github-mcp-server")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_prs",
            description="List pull requests for a repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name (owner/repo)"},
                    "state": {"type": "string", "enum": ["open", "closed", "all"], "default": "open"}
                },
                "required": ["repo"]
            }
        ),
        Tool(
            name="get_pr_comments",
            description="Get all review comments on a pull request (including Copilot reviews)",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name (owner/repo)"},
                    "pr_number": {"type": "integer", "description": "Pull request number"}
                },
                "required": ["repo", "pr_number"]
            }
        ),
        Tool(
            name="get_pr_reviews",
            description="Get all reviews submitted on a pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name (owner/repo)"},
                    "pr_number": {"type": "integer", "description": "Pull request number"}
                },
                "required": ["repo", "pr_number"]
            }
        ),
        Tool(
            name="create_pr_comment",
            description="Add a comment to a pull request (Cortex's response to Copilot)",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name (owner/repo)"},
                    "pr_number": {"type": "integer", "description": "Pull request number"},
                    "body": {"type": "string", "description": "Comment text"}
                },
                "required": ["repo", "pr_number", "body"]
            }
        ),
        Tool(
            name="create_pr",
            description="Create a new pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name (owner/repo)"},
                    "title": {"type": "string", "description": "PR title"},
                    "body": {"type": "string", "description": "PR description"},
                    "head": {"type": "string", "description": "Source branch"},
                    "base": {"type": "string", "description": "Target branch (usually 'main')"}
                },
                "required": ["repo", "title", "head", "base"]
            }
        ),
        Tool(
            name="get_pr_files",
            description="Get list of files changed in a pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name (owner/repo)"},
                    "pr_number": {"type": "integer", "description": "Pull request number"}
                },
                "required": ["repo", "pr_number"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    try:
        if name == "list_prs":
            repo = gh.get_repo(arguments["repo"])
            state = arguments.get("state", "open")
            prs = repo.get_pulls(state=state)

            result = []
            for pr in prs[:10]:  # Limit to 10 most recent
                result.append({
                    "number": pr.number,
                    "title": pr.title,
                    "state": pr.state,
                    "author": pr.user.login,
                    "created_at": pr.created_at.isoformat(),
                    "url": pr.html_url
                })

            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "get_pr_comments":
            repo = gh.get_repo(arguments["repo"])
            pr = repo.get_pull(arguments["pr_number"])

            # Get review comments (code-specific)
            review_comments = []
            for comment in pr.get_review_comments():
                review_comments.append({
                    "id": comment.id,
                    "author": comment.user.login,
                    "body": comment.body,
                    "path": comment.path,
                    "line": comment.line,
                    "created_at": comment.created_at.isoformat(),
                    "is_copilot": "copilot" in comment.user.login.lower()
                })

            # Get issue comments (general PR discussion)
            issue_comments = []
            for comment in pr.get_issue_comments():
                issue_comments.append({
                    "id": comment.id,
                    "author": comment.user.login,
                    "body": comment.body,
                    "created_at": comment.created_at.isoformat(),
                    "is_copilot": "copilot" in comment.user.login.lower()
                })

            result = {
                "review_comments": review_comments,
                "issue_comments": issue_comments,
                "total_copilot_comments": sum(1 for c in review_comments + issue_comments if c["is_copilot"])
            }

            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "get_pr_reviews":
            repo = gh.get_repo(arguments["repo"])
            pr = repo.get_pull(arguments["pr_number"])

            reviews = []
            for review in pr.get_reviews():
                reviews.append({
                    "id": review.id,
                    "author": review.user.login,
                    "state": review.state,
                    "body": review.body,
                    "submitted_at": review.submitted_at.isoformat() if review.submitted_at else None,
                    "is_copilot": "copilot" in review.user.login.lower()
                })

            return [TextContent(
                type="text",
                text=json.dumps(reviews, indent=2)
            )]

        elif name == "create_pr_comment":
            repo = gh.get_repo(arguments["repo"])
            pr = repo.get_pull(arguments["pr_number"])
            comment = pr.create_issue_comment(arguments["body"])

            return [TextContent(
                type="text",
                text=f"Comment created: {comment.html_url}"
            )]

        elif name == "create_pr":
            repo = gh.get_repo(arguments["repo"])
            pr = repo.create_pull(
                title=arguments["title"],
                body=arguments["body"],
                head=arguments["head"],
                base=arguments.get("base", "main")
            )

            return [TextContent(
                type="text",
                text=json.dumps({
                    "number": pr.number,
                    "url": pr.html_url,
                    "state": pr.state
                }, indent=2)
            )]

        elif name == "get_pr_files":
            repo = gh.get_repo(arguments["repo"])
            pr = repo.get_pull(arguments["pr_number"])

            files = []
            for file in pr.get_files():
                files.append({
                    "filename": file.filename,
                    "status": file.status,
                    "additions": file.additions,
                    "deletions": file.deletions,
                    "changes": file.changes,
                    "patch": file.patch[:500] if file.patch else None  # Truncate for safety
                })

            return [TextContent(
                type="text",
                text=json.dumps(files, indent=2)
            )]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except GithubException as e:
        return [TextContent(
            type="text",
            text=f"GitHub API error: {e.status} - {e.data.get('message', str(e))}"
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]

if __name__ == "__main__":
    import asyncio
    from mcp.server.stdio import stdio_server

    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )

    asyncio.run(main())
```

---

### Phase 3: Workflow Implementation

**Cortex's Workflow** (when making code changes):

1. **Write code normally** (as I do now)
2. **Create a feature branch** instead of committing to main:
   ```bash
   git checkout -b feature/cortex-optimization-$(date +%s)
   git add .
   git commit -m "..."
   git push origin feature/cortex-optimization-$(date +%s)
   ```
3. **Create PR via GitHub MCP**:
   ```python
   create_pr(
       repo="ry-ops/cortex-gitops",
       title="Optimize cortex-school memory usage",
       body="## Changes\n- Reduced memory requests...",
       head="feature/cortex-optimization-123456",
       base="main"
   )
   ```
4. **Wait 30-60 seconds** for Copilot to review
5. **Read Copilot's feedback**:
   ```python
   comments = get_pr_comments(repo="ry-ops/cortex-gitops", pr_number=42)
   reviews = get_pr_reviews(repo="ry-ops/cortex-gitops", pr_number=42)
   ```
6. **Analyze and respond**:
   - Good suggestion? Update code and push
   - Pattern to learn? Document in memory
   - Context-specific? Explain via comment

---

### Phase 4: Learning Loop

**Pattern Recognition**:

Cortex maintains a **pattern database** in memory:

```python
LEARNED_PATTERNS = {
    "kubernetes": {
        "imagePullPolicy": {
            "preferred": "IfNotPresent",
            "reason": "Reduces registry load, Copilot suggested 2026-01-15",
            "exceptions": ["always pull for :latest tags"]
        },
        "resource_limits": {
            "pattern": "limits should be 2-4x requests",
            "reason": "Copilot flagged over-limiting on PR#42",
            "source": "copilot-review-2026-01-15"
        }
    },
    "github_actions": {
        "preferred_actions": [
            "actions/checkout@v4 (not v3)",
            "actions/setup-python@v5"
        ],
        "reason": "Copilot security recommendations"
    }
}
```

**When Cortex writes new code**, it checks this database first.

---

### Phase 5: Automated Response System

**Goal**: Cortex automatically incorporates valid Copilot suggestions

```python
async def process_copilot_feedback(pr_number: int):
    """
    Automatically process Copilot's review on a PR
    """
    comments = await get_pr_comments("ry-ops/cortex-gitops", pr_number)

    for comment in comments["review_comments"]:
        if not comment["is_copilot"]:
            continue

        # Parse Copilot's suggestion
        suggestion = parse_copilot_suggestion(comment["body"])

        # Evaluate against cluster context
        if is_valid_for_cluster(suggestion):
            # Apply suggestion
            apply_code_change(
                file=comment["path"],
                line=comment["line"],
                change=suggestion["code"]
            )

            # Respond to Copilot
            await create_pr_comment(
                repo="ry-ops/cortex-gitops",
                pr_number=pr_number,
                body=f"✅ Applied Copilot's suggestion: {suggestion['summary']}\n\n"
                     f"Validated against cluster context and committed."
            )
        else:
            # Explain why not applicable
            await create_pr_comment(
                repo="ry-ops/cortex-gitops",
                pr_number=pr_number,
                body=f"❌ Copilot's suggestion not applicable: {suggestion['summary']}\n\n"
                     f"**Reason**: {get_context_reason(suggestion)}\n\n"
                     f"**Cluster Context**: {get_current_cluster_state()}"
            )
```

---

## 🎯 Success Criteria

**Phase 1 Complete When**:
- ✅ GitHub Copilot for PRs enabled on repos
- ✅ GitHub MCP server deployed and healthy
- ✅ Can create PRs programmatically
- ✅ Can read Copilot review comments

**Phase 2 Complete When**:
- ✅ Cortex creates feature branch + PR automatically
- ✅ Copilot reviews PR within 60 seconds
- ✅ Cortex reads and displays Copilot suggestions
- ✅ Manual validation: suggestions make sense

**Phase 3 Complete When**:
- ✅ Cortex automatically applies valid suggestions
- ✅ Cortex explains rejected suggestions with context
- ✅ Pattern database populated with learnings
- ✅ Future PRs show improved code quality

---

## 📊 Metrics to Track

1. **PR Review Time**: Time from PR creation to Copilot review
2. **Suggestion Acceptance Rate**: % of Copilot suggestions applied
3. **Pattern Learning**: # of patterns learned per week
4. **Code Quality Improvement**: Reduced iterations per PR over time
5. **Context Conflicts**: # of suggestions rejected due to cluster context

---

## 🔍 Example Interaction

**Scenario**: Cortex optimizes a deployment

```
[Cortex writes code]
├── apps/cortex-school/moe-router-deployment.yaml
│   - Reduces memory: 256Mi → 128Mi
│   - Adds securityContext
│   - Updates image pull policy

[Cortex creates PR]
├── Branch: feature/moe-router-optimization-1737012345
├── PR: "Optimize moe-router memory and security"
└── Waits for Copilot...

[Copilot reviews (60 seconds later)]
├── Comment 1: "Consider using readOnlyRootFilesystem: true"
├── Comment 2: "imagePullPolicy: Always is better for :latest tags"
└── Comment 3: "Add resource limits, not just requests"

[Cortex analyzes]
├── Comment 1: ✅ Valid - Apply
│   └── Adds readOnlyRootFilesystem: true
├── Comment 2: ❌ Context-specific - Explain
│   └── "Using IfNotPresent because image is tagged v1.2.3, not :latest"
├── Comment 3: ✅ Valid - Apply
│   └── Adds limits: memory: 512Mi, cpu: 500m

[Cortex updates PR]
├── Pushes new commit with changes
├── Comments explaining decisions
└── Learns pattern: "Always add resource limits"

[Copilot approves]
└── PR merged to main

[ArgoCD deploys]
└── Changes live in 3 minutes
```

---

## 🚀 Next Steps

1. **User Action Required**: Enable GitHub Copilot for Pull Requests
   - Go to: https://github.com/ry-ops/cortex-gitops/settings
   - Enable: "GitHub Copilot" → "Pull Request Reviews"
   - Repeat for: cortex-platform

2. **Cortex Action**: Deploy GitHub MCP server
   - Create ConfigMap with github-mcp-server.py
   - Deploy service and deployment
   - Test connectivity

3. **Cortex Action**: Create test PR
   - Make small change to trigger Copilot
   - Read Copilot's feedback
   - Document interaction pattern

4. **Iterate**: Refine based on results

---

## 📚 References

- GitHub Copilot for PRs: https://github.com/features/copilot
- PyGithub Library: https://pygithub.readthedocs.io/
- MCP Protocol: https://modelcontextprotocol.io/

---

**Status**: Ready for implementation once Copilot for PRs is enabled

**Author**: Claude Sonnet 4.5 (Cortex Control Plane)
**Collaboration**: Human + Claude + Copilot (AI²)
