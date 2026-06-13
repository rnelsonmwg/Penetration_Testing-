from __future__ import annotations

from collections import Counter

from app.agents.base import AgentContext, BaseAgent
from app.models.schemas import Finding


class ReconAgent(BaseAgent):
    name = "recon"
    description = "Passive attack-surface and asset enumeration from imported materials."

    def run(self, context: AgentContext) -> list[Finding]:
        endpoints = self.endpoints(context)
        findings: list[Finding] = []
        hosts = Counter(e.get("host") or (e.get("base_urls") or [None])[0] or "unknown" for e in endpoints)
        methods = Counter(e.get("method", "GET") for e in endpoints)
        if endpoints:
            findings.append(
                Finding(
                    title="Imported attack surface inventory created",
                    severity="info",
                    category="reconnaissance",
                    description=f"Khepri Nyame mapped {len(endpoints)} imported endpoint(s) across {len(hosts)} host/base URL value(s).",
                    evidence=[f"HTTP methods observed: {dict(methods)}", f"Top host/base values: {dict(hosts.most_common(5))}"],
                    remediation="Review the discovered endpoint inventory, remove out-of-scope entries, and enrich targets with ownership metadata.",
                    confidence="high",
                )
            )
        else:
            findings.append(
                Finding(
                    title="No imported endpoints available for passive recon",
                    severity="info",
                    category="reconnaissance",
                    description="No OpenAPI, Postman, HAR, Burp, GraphQL, or URL data has been imported yet.",
                    remediation="Import at least one API or web asset source before running deeper workflow agents.",
                    confidence="high",
                )
            )
        return findings
