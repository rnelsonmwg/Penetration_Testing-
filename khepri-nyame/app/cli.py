from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from app.agents.base import AgentContext
from app.agents.orchestrator import run_agents
from app.ai.providers import get_provider
from app.core.config import settings
from app.models.schemas import Engagement, EngagementCreate, ExperienceMode, ImportRequest, ProviderName, ThemeName
from app.parsers.input_parsers import parse_import
from app.reporting.exporters import export_report
from app.storage.json_store import JsonStore

app = typer.Typer(help="Khepri Nyame: local-first safe bug hunting/API security testing assistant.")
console = Console()
store = JsonStore(settings.storage_dir)


@app.command()
def init(
    name: str = typer.Option(..., help="Engagement name."),
    scope: list[str] = typer.Option(..., help="In-scope asset. Repeat for multiple."),
    authorization: str = typer.Option(..., help="Authorization statement."),
    mode: ExperienceMode = ExperienceMode.guided_wizard,
    theme: ThemeName = ThemeName.clean_enterprise,
    provider: ProviderName = ProviderName.local_rule_based,
) -> None:
    payload = EngagementCreate(name=name, scope=scope, authorization_statement=authorization, mode=mode, theme=theme, provider=provider)
    engagement = Engagement(**payload.model_dump())
    data = engagement.model_dump()
    data.update({"imports": [], "findings": [], "plans": []})
    store.save("engagements", engagement.id, data)
    console.print(f"[bold green]Created engagement[/bold green] {engagement.name} ({engagement.id})")


@app.command("list")
def list_engagements() -> None:
    table = Table("ID", "Name", "Mode", "Theme", "Provider", "Scope")
    for engagement in store.list("engagements"):
        table.add_row(engagement["id"], engagement["name"], engagement["mode"], engagement["theme"], engagement["provider"], ", ".join(engagement.get("scope", [])))
    console.print(table)


@app.command()
def import_file(
    engagement_id: str,
    source_type: str = typer.Option(..., help="openapi, postman, har, burp, graphql, raw_url, or notes"),
    path: Path = typer.Option(..., exists=True, dir_okay=False),
    name: Optional[str] = None,
) -> None:
    engagement = store.load("engagements", engagement_id)
    content = path.read_text(encoding="utf-8")
    endpoints, metadata = parse_import(source_type, content)
    imported = {
        "id": path.stem,
        "source_type": source_type,
        "name": name or path.name,
        "raw_preview": content[:50000],
        "endpoints": endpoints,
        "metadata": metadata,
    }
    engagement.setdefault("imports", []).append(imported)
    store.save("engagements", engagement_id, engagement)
    console.print(f"[green]Imported[/green] {len(endpoints)} endpoint(s) from {path}")


@app.command()
def plan(engagement_id: str) -> None:
    engagement = store.load("engagements", engagement_id)
    provider = get_provider(engagement.get("provider", settings.default_provider))
    generated = asyncio.run(provider.generate_plan(engagement, engagement.get("imports", [])))
    engagement.setdefault("plans", []).append(generated.model_dump())
    store.save("engagements", engagement_id, engagement)
    table = Table("Agent", "Goal", "Active")
    for step in generated.steps:
        table.add_row(step.get("agent", ""), step.get("goal", ""), str(step.get("active", False)))
    console.print(table)
    for note in generated.safety_notes:
        console.print(f"[yellow]Safety:[/yellow] {note}")


@app.command()
def run(engagement_id: str) -> None:
    engagement = store.load("engagements", engagement_id)
    context = AgentContext(engagement=engagement, imports=engagement.get("imports", []), findings=engagement.get("findings", []))
    findings = run_agents(context)
    engagement["findings"] = context.get("findings", [])
    store.save("engagements", engagement_id, engagement)
    table = Table("Severity", "Category", "Title")
    for finding in findings:
        table.add_row(finding.severity, finding.category, finding.title)
    console.print(table)


@app.command()
def report(engagement_id: str, fmt: str = "markdown", output: Path = Path("khepri-report.md")) -> None:
    engagement = store.load("engagements", engagement_id)
    content, _media_type, _extension = export_report(engagement, fmt)
    if isinstance(content, bytes):
        output.write_bytes(content)
    else:
        output.write_text(content, encoding="utf-8")
    console.print(f"[green]Wrote report[/green] {output}")


if __name__ == "__main__":
    app()
