from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent
from app.core.safety import find_possible_secrets
from app.models.schemas import Finding


class SecretReviewAgent(BaseAgent):
    name = "secret_review"
    description = "Passive API key/token leakage review over imported text."

    def run(self, context: AgentContext) -> list[Finding]:
        findings: list[Finding] = []
        evidence: list[str] = []
        for imported in context.get("imports", []):
            preview = imported.get("raw_preview") or ""
            for secret in find_possible_secrets(preview):
                evidence.append(f"{imported.get('name')}: {secret}")
        if evidence:
            findings.append(
                Finding(
                    title="Possible secret material found in imported artifacts",
                    severity="high",
                    category="secret-leakage",
                    description="Imported API artifacts appear to contain token, key, secret, or credential-like strings. Evidence is redacted.",
                    evidence=evidence[:50],
                    safe_validation="Confirm whether each redacted value is real in a secure credential-management process; do not use or replay discovered secrets.",
                    remediation="Revoke exposed secrets, rotate credentials, remove secrets from collections/specs, and use vault-backed environment variables.",
                    confidence="medium",
                )
            )
        return findings
