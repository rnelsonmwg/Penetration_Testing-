from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from html import escape
from typing import Any

try:
    import markdown as md
except Exception:  # pragma: no cover - optional dependency fallback
    md = None

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
except Exception:  # pragma: no cover - optional dependency fallback
    letter = None
    canvas = None

SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]


def export_report(engagement: dict[str, Any], fmt: str) -> tuple[str | bytes, str, str]:
    fmt = fmt.lower()
    if fmt == "markdown":
        return render_markdown(engagement), "text/markdown", "md"
    if fmt == "html":
        return render_html(engagement), "text/html", "html"
    if fmt == "pdf":
        return render_pdf(engagement), "application/pdf", "pdf"
    if fmt == "json":
        return json.dumps(engagement, indent=2, sort_keys=True), "application/json", "json"
    if fmt == "csv":
        return render_csv(engagement), "text/csv", "csv"
    if fmt == "executive":
        return render_executive(engagement), "text/markdown", "md"
    if fmt == "jira":
        return render_jira(engagement), "text/plain", "txt"
    if fmt == "github":
        return render_github_issue(engagement), "text/markdown", "md"
    raise ValueError(f"Unsupported report format: {fmt}")


def _findings(engagement: dict[str, Any]) -> list[dict[str, Any]]:
    return engagement.get("findings", [])


def render_markdown(engagement: dict[str, Any]) -> str:
    findings = _findings(engagement)
    lines = [
        f"# Khepri Nyame Report: {engagement.get('name', 'Engagement')}",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Mode: `{engagement.get('mode')}`  ",
        f"Provider: `{engagement.get('provider')}`  ",
        "",
        "## Scope",
        "",
    ]
    for item in engagement.get("scope", []):
        lines.append(f"- {item}")
    lines += ["", "## Safety Boundary", "", "This report is generated for authorized assets only. The MVP avoids exploit execution, credential attacks, brute force, stealth, persistence, destructive actions, and data extraction.", "", "## Findings", ""]
    for severity in SEVERITY_ORDER:
        sev_findings = [f for f in findings if f.get("severity") == severity]
        if not sev_findings:
            continue
        lines.append(f"### {severity.title()}")
        lines.append("")
        for finding in sev_findings:
            lines.extend(_finding_markdown(finding))
    return "\n".join(lines).strip() + "\n"


def _finding_markdown(finding: dict[str, Any]) -> list[str]:
    lines = [
        f"#### {finding.get('title')}",
        "",
        f"- **Category:** {finding.get('category')}",
        f"- **Severity:** {finding.get('severity')}",
        f"- **Confidence:** {finding.get('confidence')}",
        f"- **Description:** {finding.get('description')}",
    ]
    if finding.get("affected_assets"):
        lines.append(f"- **Affected assets:** {', '.join(finding['affected_assets'])}")
    if finding.get("safe_validation"):
        lines.append(f"- **Safe validation:** {finding.get('safe_validation')}")
    if finding.get("remediation"):
        lines.append(f"- **Remediation:** {finding.get('remediation')}")
    evidence = finding.get("evidence") or []
    if evidence:
        lines += ["", "Evidence:"]
        for item in evidence[:20]:
            lines.append(f"- `{item}`")
    lines.append("")
    return lines


def render_html(engagement: dict[str, Any]) -> str:
    markdown_text = render_markdown(engagement)
    if md is not None:
        body = md.markdown(markdown_text, extensions=["tables", "fenced_code"])
    else:
        body = "<pre>" + escape(markdown_text) + "</pre>"
    return f"""<!doctype html>
<html lang=\"en\">
<head><meta charset=\"utf-8\"><title>Khepri Nyame Report</title>
<style>
body {{ font-family: Inter, system-ui, sans-serif; max-width: 980px; margin: 40px auto; line-height: 1.55; }}
code {{ background: #f3f4f6; padding: 2px 5px; border-radius: 4px; }}
h1, h2, h3 {{ color: #1f2937; }}
</style></head>
<body>{body}</body></html>"""


def render_pdf(engagement: dict[str, Any]) -> bytes:
    if canvas is None or letter is None:
        # Minimal fallback so the exporter remains usable before optional deps are installed.
        return render_markdown(engagement).encode("utf-8")
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 54
    text = render_markdown(engagement)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(54, y, f"Khepri Nyame Report: {engagement.get('name', 'Engagement')}")
    y -= 28
    c.setFont("Helvetica", 9)
    for line in text.splitlines()[1:]:
        if y < 54:
            c.showPage()
            c.setFont("Helvetica", 9)
            y = height - 54
        clean = line.replace("#", "").replace("`", "")
        c.drawString(54, y, clean[:110])
        y -= 12
    c.save()
    return buffer.getvalue()


def render_csv(engagement: dict[str, Any]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id", "title", "severity", "category", "confidence", "description", "safe_validation", "remediation"])
    writer.writeheader()
    for finding in _findings(engagement):
        writer.writerow({field: finding.get(field, "") for field in writer.fieldnames})
    return output.getvalue()


def render_executive(engagement: dict[str, Any]) -> str:
    findings = _findings(engagement)
    counts = {s: sum(1 for f in findings if f.get("severity") == s) for s in SEVERITY_ORDER}
    top = sorted(findings, key=lambda f: SEVERITY_ORDER.index(f.get("severity", "info")) if f.get("severity", "info") in SEVERITY_ORDER else 99)[:5]
    lines = [
        f"# Executive Summary: {engagement.get('name', 'Engagement')}",
        "",
        "Khepri Nyame completed a safe, local-first analysis of imported bug hunting and API security artifacts.",
        "",
        "## Severity Summary",
        "",
    ]
    for severity in SEVERITY_ORDER:
        lines.append(f"- {severity.title()}: {counts[severity]}")
    lines += ["", "## Top Review Items", ""]
    for finding in top:
        lines.append(f"- **{finding.get('severity', 'info').title()}** — {finding.get('title')}: {finding.get('description')}")
    lines += ["", "## Recommended Next Step", "", "Validate high-confidence authorization, secret exposure, SSRF/open redirect, injection, and mass-assignment candidates in approved test environments only."]
    return "\n".join(lines) + "\n"


def render_jira(engagement: dict[str, Any]) -> str:
    lines = [f"h1. Khepri Nyame Findings: {engagement.get('name', 'Engagement')}", ""]
    for finding in _findings(engagement):
        lines.extend([
            f"h2. [{finding.get('severity', 'info').upper()}] {finding.get('title')}",
            f"*Category:* {finding.get('category')}",
            f"*Confidence:* {finding.get('confidence')}",
            f"*Description:* {finding.get('description')}",
            f"*Safe validation:* {finding.get('safe_validation', 'N/A')}",
            f"*Remediation:* {finding.get('remediation', 'N/A')}",
            "",
        ])
    return "\n".join(lines)


def render_github_issue(engagement: dict[str, Any]) -> str:
    findings = _findings(engagement)
    lines = [
        f"# Khepri Nyame Security Review: {escape(engagement.get('name', 'Engagement'))}",
        "",
        "## Checklist",
        "",
    ]
    for finding in findings:
        lines.append(f"- [ ] **{finding.get('severity', 'info').upper()}** {finding.get('title')}")
    lines += ["", "## Details", "", render_markdown(engagement)]
    return "\n".join(lines)
