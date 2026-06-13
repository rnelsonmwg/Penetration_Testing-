from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent
from app.models.schemas import Finding

SEVERITY_ORDER = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}


class RiskPrioritizationAgent(BaseAgent):
    name = "risk"
    description = "Normalizes findings into review priority and executive context."

    def run(self, context: AgentContext) -> list[Finding]:
        existing = [Finding(**f) if isinstance(f, dict) else f for f in context.get("findings", [])]
        if not existing:
            return []
        counts = {severity: 0 for severity in SEVERITY_ORDER}
        for finding in existing:
            counts[finding.severity] += 1
        top = sorted(existing, key=lambda f: SEVERITY_ORDER[f.severity], reverse=True)[:5]
        return [
            Finding(
                title="Prioritized bug hunting review queue generated",
                severity="info",
                category="risk-prioritization",
                description="Findings have been grouped into a safe validation queue, with higher-risk API authorization, secret leakage, SSRF, and mass-assignment issues prioritized first.",
                evidence=[f"Severity counts: {counts}"] + [f"{f.severity.upper()}: {f.title}" for f in top],
                remediation="Validate high-priority items first in approved environments, then convert confirmed issues into tickets with owner, remediation SLA, and regression test coverage.",
                confidence="high",
            )
        ]
