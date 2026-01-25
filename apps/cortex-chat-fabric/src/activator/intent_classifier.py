#!/usr/bin/env python3
"""
Intent Classifier - Determines which fabric should handle a query

Uses Claude Haiku for fast intent classification, with keyword fallback.
"""
from typing import Dict, Any, Optional

from anthropic import AsyncAnthropic
import structlog

logger = structlog.get_logger()


class IntentClassifier:
    """
    Classifies user intents to route to appropriate fabrics.

    Uses a two-tier approach:
    1. Fast keyword matching
    2. Claude Haiku for ambiguous queries
    """

    # Keyword mappings for fast classification
    KEYWORD_MAPPINGS = {
        "unifi": {
            "keywords": [
                "unifi", "network", "wifi", "wireless", "client", "device",
                "ap", "access point", "switch", "gateway", "usg", "udm",
                "ssid", "vlan", "bandwidth", "throughput", "connected",
                "internet", "wan", "lan", "dhcp"
            ],
            "expert": "network",
            "fabric": "unifi"
        },
        "proxmox": {
            "keywords": [
                "proxmox", "vm", "virtual machine", "lxc", "pve",
                "storage", "backup", "snapshot", "template"
            ],
            "expert": "proxmox",
            "fabric": "proxmox"
        },
        "kubernetes": {
            "keywords": [
                "kubernetes", "k8s", "pod", "pods", "deploy", "deployment",
                "service", "ingress", "namespace", "kubectl", "helm",
                "replica", "scaling", "argocd", "node", "nodes"
            ],
            "expert": "kubernetes",
            "fabric": "kubernetes"
        },
        "github": {
            "keywords": [
                "github", "repo", "repository", "issue", "issues", "pr",
                "pull request", "commit", "commits", "branch", "branches",
                "workflow", "action", "release", "merge", "code review"
            ],
            "expert": "github",
            "fabric": "github"
        },
        "cloudflare": {
            "keywords": [
                "cloudflare", "dns", "tunnel", "waf", "zone", "zones",
                "cache", "purge", "edge", "cdn", "ssl", "certificate"
            ],
            "expert": "cloudflare",
            "fabric": "cloudflare"
        },
        "sandfly": {
            "keywords": [
                "sandfly", "scan", "host scan", "threat", "alert", "alerts",
                "host security", "compliance", "forensic", "security scan"
            ],
            "expert": "sandfly",
            "fabric": "sandfly"
        },
        "cortex": {
            "keywords": [
                "cortex", "agent", "fabric", "status", "help", "what can",
                "system", "registry"
            ],
            "expert": "cortex",
            "fabric": "cortex"
        },
        "automation": {
            "keywords": [
                "n8n", "automate", "automation", "langflow",
                "trigger", "schedule", "cron", "webhook"
            ],
            "expert": "automation",
            "fabric": None  # No fabric yet
        }
    }

    def __init__(self, api_key: str, fabric_dispatcher=None):
        self.api_key = api_key
        self.fabric_dispatcher = fabric_dispatcher
        self._client = None

    @property
    def client(self) -> AsyncAnthropic:
        if not self._client:
            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def classify(self, message: str) -> Dict[str, Any]:
        """
        Classify a message to determine routing.

        Returns:
            Dict with 'expert', 'fabric', and 'confidence' keys
        """
        message_lower = message.lower()

        # First try fast keyword matching
        for category, config in self.KEYWORD_MAPPINGS.items():
            for keyword in config["keywords"]:
                if keyword in message_lower:
                    logger.info("intent_classified_by_keyword",
                                keyword=keyword,
                                category=category)
                    return {
                        "expert": config["expert"],
                        "fabric": config.get("fabric"),
                        "confidence": 0.9,
                        "method": "keyword"
                    }

        # If no keyword match, try Claude Haiku for better classification
        if self.api_key:
            try:
                result = await self._classify_with_claude(message)
                if result:
                    return result
            except Exception as e:
                logger.error("claude_classification_error", error=str(e))

        # Default to general
        return {
            "expert": "general",
            "fabric": None,
            "confidence": 0.5,
            "method": "default"
        }

    async def _classify_with_claude(self, message: str) -> Optional[Dict[str, Any]]:
        """Use Claude Haiku for intent classification."""
        prompt = f"""Classify this user message into one of these categories:
- network: UniFi network, WiFi, clients, devices, internet, bandwidth
- proxmox: Proxmox VMs, containers, LXC, PVE, storage, backups
- kubernetes: Kubernetes pods, deployments, services, ingresses, namespaces
- github: GitHub repos, issues, PRs, commits, branches, workflows
- cloudflare: DNS, tunnels, WAF, zones, cache, CDN
- sandfly: Sandfly scans, threats, alerts, host security, compliance
- cortex: System status, agents, fabrics, help, what can you do
- automation: n8n workflows, automation, scheduling
- general: General conversation, greetings, or unclear intent

User message: {message}

Respond with ONLY one word: network, proxmox, kubernetes, github, cloudflare, sandfly, cortex, automation, or general"""

        response = await self.client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}]
        )

        category = response.content[0].text.strip().lower()

        # Map category to expert and fabric
        category_map = {
            "network": {"expert": "network", "fabric": "unifi"},
            "proxmox": {"expert": "proxmox", "fabric": "proxmox"},
            "kubernetes": {"expert": "kubernetes", "fabric": "kubernetes"},
            "github": {"expert": "github", "fabric": "github"},
            "cloudflare": {"expert": "cloudflare", "fabric": "cloudflare"},
            "sandfly": {"expert": "sandfly", "fabric": "sandfly"},
            "cortex": {"expert": "cortex", "fabric": "cortex"},
            "automation": {"expert": "automation", "fabric": None},
            "general": {"expert": "general", "fabric": None}
        }

        if category in category_map:
            result = category_map[category]
            result["confidence"] = 0.85
            result["method"] = "claude"
            logger.info("intent_classified_by_claude", category=category)
            return result

        return None
