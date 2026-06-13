from __future__ import annotations

import re
from urllib.parse import parse_qs

from app.agents.base import AgentContext, BaseAgent
from app.models.schemas import Finding

RESOURCE_ID_TERMS = re.compile(r"(?i)(user|account|tenant|org|organization|project|customer|invoice|order|case|ticket|document|file|report).*id|{[^}]*id[^}]*}")
URL_PARAM_TERMS = {"url", "uri", "redirect", "next", "return", "callback", "webhook", "target", "path", "file"}
MASS_ASSIGNMENT_TERMS = {"role", "isadmin", "admin", "permission", "permissions", "plan", "tier", "owner", "verified", "balance"}
INJECTION_TERMS = {"q", "query", "search", "filter", "sort", "where", "select", "sql", "cmd"}


class AuthzTesterAgent(BaseAgent):
    name = "authz"
    description = "Safe authorization and API weakness analysis using imported definitions and examples."

    def run(self, context: AgentContext) -> list[Finding]:
        findings: list[Finding] = []
        endpoints = self.endpoints(context)
        bola_candidates = []
        ssrf_candidates = []
        injection_candidates = []
        mass_assignment_candidates = []

        for endpoint in endpoints:
            method = endpoint.get("method", "GET")
            path = str(endpoint.get("path", ""))
            label = f"{method} {path}"
            if RESOURCE_ID_TERMS.search(path):
                bola_candidates.append(label)
            query = endpoint.get("query") or ""
            qs = parse_qs(query)
            params = {str(p.get("name", "")).lower() for p in endpoint.get("parameters", []) if isinstance(p, dict)} | {k.lower() for k in qs.keys()}
            lowered_path = path.lower()
            if params & URL_PARAM_TERMS or any(term in lowered_path for term in ["callback", "redirect", "webhook"]):
                ssrf_candidates.append(label)
            if params & INJECTION_TERMS:
                injection_candidates.append(label)
            if params & MASS_ASSIGNMENT_TERMS or endpoint.get("request_body_present"):
                # request body presence is not a vulnerability, just a review cue.
                mass_assignment_candidates.append(label)

        if bola_candidates:
            findings.append(
                Finding(
                    title="BOLA/BFLA review candidates identified",
                    severity="high",
                    category="authorization",
                    description="Resource identifiers appear in API routes. These endpoints should be reviewed for object-level and function-level authorization gaps using approved test identities only.",
                    evidence=bola_candidates[:30],
                    safe_validation="Create two approved test users with separate resources. Confirm that each route rejects access to the other user's resource without altering production data.",
                    remediation="Enforce server-side ownership checks and role checks on every resource-accessing route, not only in the UI or gateway.",
                    confidence="medium",
                )
            )
        if ssrf_candidates:
            findings.append(
                Finding(
                    title="URL-like parameters or callback routes require SSRF/open redirect review",
                    severity="medium",
                    category="ssrf-open-redirect",
                    description="Imported routes contain URL, redirect, callback, webhook, or target-like inputs. These can become SSRF or open redirect issues if not constrained.",
                    evidence=ssrf_candidates[:30],
                    safe_validation="Use a controlled benign callback domain and do not target third-party/internal hosts. Confirm allowlist and scheme restrictions only.",
                    remediation="Allowlist trusted destinations, block link-local/private IP ranges, normalize DNS, and disallow unsafe URL schemes.",
                    confidence="medium",
                )
            )
        if injection_candidates:
            findings.append(
                Finding(
                    title="Search/filter parameters require injection review",
                    severity="medium",
                    category="injection",
                    description="Search, query, filter, or sort-style parameters are present. These should be tested safely for server-side parsing or query construction flaws.",
                    evidence=injection_candidates[:30],
                    safe_validation="Use non-destructive canary strings in a test tenant only. Do not attempt destructive database, command, or file-system actions.",
                    remediation="Use parameterized queries, strict schema validation, output encoding, and centralized input validation.",
                    confidence="low",
                )
            )
        if mass_assignment_candidates:
            findings.append(
                Finding(
                    title="Request bodies require mass-assignment and excessive-property review",
                    severity="medium",
                    category="mass-assignment",
                    description="Routes with request bodies or sensitive parameter names should be reviewed for over-posting, privilege field assignment, and schema drift.",
                    evidence=mass_assignment_candidates[:30],
                    safe_validation="Compare accepted fields against the public schema using a test tenant. Do not attempt privilege changes outside approved lab accounts.",
                    remediation="Use explicit allowlists for mutable fields and reject or ignore privileged server-controlled properties.",
                    confidence="medium",
                )
            )
        return findings
