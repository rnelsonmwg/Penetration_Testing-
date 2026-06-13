"""Report generation: Markdown for humans, JSON for tooling."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from ..core.models import Run, Severity

_SEV_BADGE = {
    Severity.CRITICAL: "🔴 CRITICAL",
    Severity.HIGH: "🟠 HIGH",
    Severity.MEDIUM: "🟡 MEDIUM",
    Severity.LOW: "🔵 LOW",
    Severity.INFO: "⚪ INFO",
}


class Reporter:
    def to_json(self, run: Run) -> str:
        return run.model_dump_json(indent=2)

    def to_markdown(self, run: Run, engagement: str = "") -> str:
        sev = run.severity_counts()
        assets = run.asset_counts()
        lines: list[str] = []
        a = lines.append

        a(f"# Thothansi Recon Report — {run.id}")
        a("")
        if engagement:
            a(f"**Engagement:** {engagement}  ")
        a(f"**Targets:** {', '.join(run.targets)}  ")
        a(f"**Generated:** {datetime.now(timezone.utc).isoformat()}  ")
        a("")
        a("> Authorized passive reconnaissance only. Findings are leads for "
          "manual verification, not confirmed vulnerabilities.")
        a("")

        a("## Summary")
        a("")
        a("| Severity | Count |")
        a("| --- | --- |")
        for s in reversed(list(Severity)):
            a(f"| {_SEV_BADGE[s]} | {sev[s.value]} |")
        a("")
        a("**Assets discovered:** " + ", ".join(
            f"{k}: {v}" for k, v in sorted(assets.items())
        ) or "none")
        a("")

        a("## Findings")
        a("")
        findings = run.all_findings()
        if not findings:
            a("_No findings recorded._")
        for f in findings:
            es = f.effective_severity
            a(f"### {_SEV_BADGE[es]} — {f.title}")
            a("")
            if f.asset:
                a(f"- **Asset:** `{f.asset}`")
            a(f"- **Source module:** `{f.source}`")
            if f.tags:
                a(f"- **Tags:** {', '.join(f.tags)}")
            if f.severity != es:
                a(f"- **Severity:** {f.severity.value} → **{es.value}** (AI-adjusted)")
            a("")
            if f.description:
                a(f.description)
                a("")
            if f.triage_rationale:
                a(f"**Analyst note:** {f.triage_rationale}")
                a("")
            if f.triage_recommendation:
                a(f"**Suggested next step:** {f.triage_recommendation}")
                a("")
            if f.triage_confidence is not None:
                a(f"_Confidence: {f.triage_confidence:.0%}_")
                a("")

        a("## Asset Inventory")
        a("")
        for asset in sorted(run.all_assets(), key=lambda x: (x.type.value, x.value)):
            a(f"- `{asset.type.value}` **{asset.value}** _(via {asset.source})_")
        a("")
        return "\n".join(lines)
