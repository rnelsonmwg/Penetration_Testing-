"""
AI-assisted triage.

Takes the raw findings from recon and asks the active AI provider to act as a
senior application-security analyst: re-rank severity, explain *why* a finding
matters for this specific attack surface, and suggest a concrete (defensive,
non-weaponized) next verification step.

The model is asked to return strict JSON so the result maps cleanly back onto
:class:`Finding`. If the provider is unavailable or returns unparseable output,
triage degrades gracefully: findings keep their heuristic severity and are
flagged as un-triaged rather than dropped.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from ..core.models import Finding, Run, Severity
from ..providers import AIProvider, ProviderError

SYSTEM_PROMPT = (
    "You are a senior application-security analyst supporting an AUTHORIZED bug "
    "bounty / penetration-testing engagement. You receive passive reconnaissance "
    "findings and assess them. For each finding return a severity, a short "
    "rationale tied to the concrete evidence, and a NON-DESTRUCTIVE next "
    "verification step a tester could take. Never provide exploit code, payloads, "
    "or instructions to compromise a system. Respond ONLY with the requested JSON."
)

_PROMPT_TEMPLATE = """\
Engagement context: passive recon results below. Assess each finding.

Allowed severity values: info, low, medium, high, critical.

Return ONLY a JSON array. Each element must be an object with keys:
  "id"            - the finding id, copied verbatim
  "severity"      - your reassessed severity
  "rationale"     - 1-2 sentences, grounded in the evidence
  "recommendation"- a non-destructive verification step
  "confidence"    - a number from 0.0 to 1.0

Findings:
{findings_json}
"""


def _finding_payload(f: Finding) -> dict:
    return {
        "id": f.id,
        "title": f.title,
        "description": f.description,
        "heuristic_severity": f.severity.value,
        "asset": f.asset,
        "tags": f.tags,
        "evidence": f.evidence,
    }


def _extract_json_array(text: str) -> list[dict]:
    """Pull the first JSON array out of a model response, tolerating fences."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "findings" in data:
            return data["findings"]
    except json.JSONDecodeError:
        pass
    # Fallback: grab the outermost [...] block.
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return []
    return []


class TriageAnalyzer:
    def __init__(self, provider: AIProvider, batch_size: int = 20):
        self.provider = provider
        self.batch_size = batch_size

    def triage_run(self, run: Run) -> Run:
        findings = run.all_findings()
        if not findings:
            return run
        by_id = {f.id: f for f in findings}

        for i in range(0, len(findings), self.batch_size):
            batch = findings[i : i + self.batch_size]
            self._triage_batch(batch, by_id)
        return run

    def _triage_batch(self, batch: list[Finding], by_id: dict[str, Finding]) -> None:
        payload = [_finding_payload(f) for f in batch]
        prompt = _PROMPT_TEMPLATE.format(findings_json=json.dumps(payload, indent=2))
        try:
            resp = self.provider.complete(prompt, system=SYSTEM_PROMPT)
        except ProviderError:
            return  # graceful: leave heuristic severities in place

        for item in _extract_json_array(resp.text):
            fid = item.get("id")
            target = by_id.get(fid)
            if not target:
                continue
            sev = self._coerce_severity(item.get("severity"))
            if sev:
                target.triage_severity = sev
            target.triage_rationale = item.get("rationale")
            target.triage_recommendation = item.get("recommendation")
            conf = item.get("confidence")
            if isinstance(conf, (int, float)):
                target.triage_confidence = float(conf)

    @staticmethod
    def _coerce_severity(value) -> Optional[Severity]:
        if not value:
            return None
        try:
            return Severity(str(value).strip().lower())
        except ValueError:
            return None
