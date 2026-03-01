# Cortex Online School

**The infrastructure that teaches itself.**

Fully autonomous system that learns from YouTube videos and automatically implements improvements to Cortex.

## Components

- **Coordinator**: Orchestrates the entire pipeline
- **MoE Router**: Routes improvements to specialized expert agents
- **RAG Validator**: Validates against existing infrastructure
- **Implementation Workers**: Generates GitOps manifests and commits changes
- **Health Monitor**: Monitors deployments and triggers rollbacks on failure
- **Qdrant**: Vector database for RAG searches

## Architecture

```
YouTube → Redis Queue → MoE → RAG → Auto-Approve → Workers → ArgoCD → Monitor
```

## Auto-Approval Criteria

- Relevance ≥ 90%
- No RAG conflicts
- Category-appropriate risk level

## Status

- **Current**: Infrastructure manifests created
- **Next**: Build container images for each service
- **Then**: Deploy via ArgoCD

## Documentation

See `/Users/ryandahlberg/Projects/cortex-docs/vault/architecture/cortex-online-school.md` for complete architecture.

## Deployment

Managed by ArgoCD via the `cortex-school` Application.

All services use images from local registry: `10.43.170.72:5000/cortex-*`
