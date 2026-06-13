from __future__ import annotations

import re
from collections import defaultdict

from app.agents.base import AgentContext, BaseAgent
from app.models.schemas import Finding

ID_PATTERN = re.compile(r"({[^}]*id[^}]*}|/[0-9a-fA-F-]{8,}|/(user|account|tenant|org|project|customer)s?/)" )
SENSITIVE_WORDS = {"admin", "internal", "debug", "token", "key", "secret", "billing", "payment", "invoice"}


class ApiMapperAgent(BaseAgent):
    name = "api_mapper"
    description = "Maps imported APIs and flags endpoints that deserve review."

    def run(self, context: AgentContext) -> list[Finding]:
        endpoints = self.endpoints(context)
        findings: list[Finding] = []
        by_path = defaultdict(set)
        interesting = []
        for endpoint in endpoints:
            path = str(endpoint.get("path", ""))
            method = str(endpoint.get("method", "GET"))
            by_path[path].add(method)
            lowered = path.lower()
            if ID_PATTERN.search(lowered) or any(word in lowered for word in SENSITIVE_WORDS):
                interesting.append(f"{method} {path}")

        multi_method_paths = [f"{','.join(sorted(methods))} {path}" for path, methods in by_path.items() if len(methods) > 2]
        if interesting:
            findings.append(
                Finding(
                    title="High-value API routes identified for authorization and data exposure review",
                    severity="medium",
                    category="api-mapping",
                    description="Several imported routes contain identifiers or sensitive business terms. These are priority candidates for safe BOLA/BFLA, data exposure, and mass-assignment review.",
                    evidence=interesting[:25],
                    safe_validation="Use only owned/approved test accounts and compare expected authorization boundaries without attempting bypass at scale.",
                    remediation="Document expected role/resource ownership rules for these routes and add automated authorization regression tests.",
                    confidence="medium",
                )
            )
        if multi_method_paths:
            findings.append(
                Finding(
                    title="Routes with broad method exposure need review",
                    severity="low",
                    category="api-mapping",
                    description="Some paths support several HTTP methods, which can indicate complex state-changing behavior or overly broad API exposure.",
                    evidence=multi_method_paths[:25],
                    safe_validation="Verify whether each method is documented, required, authenticated, and logged.",
                    remediation="Remove unnecessary methods and enforce deny-by-default authorization checks per method.",
                    confidence="medium",
                )
            )
        return findings
