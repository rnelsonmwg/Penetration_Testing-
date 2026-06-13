"""
Thothansi command-line interface.

  thothansi init                 scaffold config + example scope
  thothansi scope show|add       inspect / extend the authorized scope
  thothansi providers            show AI provider availability
  thothansi run TARGET...        run the recon -> triage -> report pipeline
  thothansi report RUN_ID        re-render a saved run as Markdown
  thothansi serve                launch the web dashboard
  thothansi tui                  launch the terminal UI
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .core import AppConfig, Engine, Scope, ScopeFileError, ScopeViolation
from .core.models import RunStage, Severity
from .core.store import RunStore
from .report import Reporter
from .theme import get_theme

app = typer.Typer(
    add_completion=False,
    help="Thothansi — AI-assisted passive recon & triage for AUTHORIZED testing.",
    no_args_is_help=True,
)
scope_app = typer.Typer(help="Manage the authorized scope.")
app.add_typer(scope_app, name="scope")

console = Console()

CONFIG_PATH = Path("config/config.yaml")
SCOPE_PATH = Path("config/scope.yaml")

_SEV_STYLE = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "bold dark_orange",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "blue",
    Severity.INFO: "dim",
}


def _load_config() -> AppConfig:
    return AppConfig.load(CONFIG_PATH if CONFIG_PATH.exists() else None)


def _load_scope() -> Scope:
    try:
        return Scope.from_file(SCOPE_PATH)
    except ScopeFileError as e:
        console.print(f"[red]Scope error:[/red] {e.message}")
        if e.hint:
            console.print(f"[yellow]{e.hint}[/yellow]")
        if e.detail:
            console.print(f"[dim]{e.detail.splitlines()[0]}[/dim]")
        raise typer.Exit(2)


def _banner(cfg: AppConfig) -> None:
    th = get_theme(cfg.theme)
    g = th["banner_glyph"]
    console.print(
        Panel.fit(
            f"[{th['rich_primary']}]{g}  THOTHANSI  {g}[/]\n"
            f"[dim]the weaver & the scribe — v{__version__}[/dim]",
            border_style=th["rich_primary"],
        )
    )


@app.command()
def init(
    force: bool = typer.Option(False, "--force", help="Overwrite existing config files.")
):
    """Scaffold config/config.yaml and config/scope.yaml."""
    Path("config").mkdir(exist_ok=True)
    from .scaffolding import CONFIG_TEMPLATE, SCOPE_TEMPLATE

    for path, content in [(CONFIG_PATH, CONFIG_TEMPLATE), (SCOPE_PATH, SCOPE_TEMPLATE)]:
        if path.exists() and not force:
            console.print(f"[yellow]exists, skipping[/yellow] {path} (use --force)")
            continue
        path.write_text(content)
        console.print(f"[green]created[/green] {path}")
    console.print(
        "\n[bold]Next:[/bold] edit [cyan]config/scope.yaml[/cyan] with the targets you are "
        "AUTHORIZED to test, then run [cyan]thothansi run <target>[/cyan]."
    )


@scope_app.command("show")
def scope_show():
    """Print the current authorized scope."""
    scope = _load_scope()
    table = Table(title=f"Scope — {scope.engagement}", show_lines=False)
    table.add_column("In-scope entry", style="green")
    for e in scope.entries:
        table.add_row(e)
    console.print(table)
    if scope.authorized_by:
        console.print(f"[dim]authorized_by: {scope.authorized_by}[/dim]")


@scope_app.command("add")
def scope_add(
    value: str = typer.Argument(..., help="domain, *.wildcard, IP, or CIDR"),
    note: str = typer.Option("", "--note", help="reason / authorization reference"),
):
    """Add an entry to the scope file (recorded in the audit log)."""
    scope = _load_scope()
    scope.add(value, note=note)
    scope.save(SCOPE_PATH)
    console.print(f"[green]added[/green] {value} to scope")


@app.command()
def providers():
    """Show which AI providers are configured and reachable."""
    cfg = _load_config()
    _banner(cfg)
    table = Table(title="AI Providers")
    table.add_column("Name")
    table.add_column("Label")
    table.add_column("Type")
    table.add_column("Model")
    table.add_column("Status")
    for p in cfg.provider_status():
        status = "[green]ready[/green]" if p["configured"] else "[red]not configured[/red]"
        active = " [bold cyan](active)[/bold cyan]" if p["active"] else ""
        table.add_row(
            p["name"] + active,
            p["label"],
            "local" if p["local"] else "remote",
            p["model"] or "-",
            status,
        )
    console.print(table)


@app.command()
def run(
    targets: list[str] = typer.Argument(..., help="In-scope domains/IPs to recon."),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Step-gate each phase (approve before running)."
    ),
    no_triage: bool = typer.Option(False, "--no-triage", help="Skip the AI triage stage."),
    provider: Optional[str] = typer.Option(None, "--provider", help="Override AI provider."),
    theme: Optional[str] = typer.Option(None, "--theme", help="modern | mythic"),
    report_out: Optional[Path] = typer.Option(
        None, "--report", help="Write a Markdown report to this path."
    ),
):
    """Run the full recon -> triage -> report pipeline against in-scope targets."""
    cfg = _load_config()
    if provider:
        cfg.active_provider = provider
    if theme:
        cfg.theme = theme
    cfg.interactive = interactive
    scope = _load_scope()
    _banner(cfg)

    def emit(stage: str, msg: str) -> None:
        console.print(f"[dim]\\[{stage}][/dim] {msg}")

    def confirm(stage: str) -> bool:
        return typer.confirm(f"Proceed with stage '{stage}'?", default=True)

    engine = Engine(cfg, scope, on_event=emit)
    try:
        run_obj = engine.run_pipeline(
            list(targets),
            interactive=interactive,
            confirm=confirm if interactive else None,
            do_triage=not no_triage,
        )
    except ScopeViolation as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    _print_summary(run_obj, cfg)
    if report_out:
        report_out.write_text(Reporter().to_markdown(run_obj, scope.engagement))
        console.print(f"\n[green]report written[/green] -> {report_out}")
    console.print(f"[dim]run id: {run_obj.id}[/dim]")


def _print_summary(run_obj, cfg) -> None:
    sev = run_obj.severity_counts()
    table = Table(title=f"Findings — run {run_obj.id}")
    table.add_column("Severity")
    table.add_column("Count", justify="right")
    for s in reversed(list(Severity)):
        table.add_row(f"[{_SEV_STYLE[s]}]{s.value}[/]", str(sev[s.value]))
    console.print(table)

    findings = run_obj.all_findings()
    if findings:
        ftable = Table(title="Top findings")
        ftable.add_column("Sev")
        ftable.add_column("Title")
        ftable.add_column("Asset", style="cyan")
        for f in findings[:15]:
            es = f.effective_severity
            ftable.add_row(f"[{_SEV_STYLE[es]}]{es.value}[/]", f.title, f.asset or "-")
        console.print(ftable)


@app.command()
def report(run_id: str = typer.Argument(..., help="A saved run id.")):
    """Print a Markdown report for a previously saved run."""
    cfg = _load_config()
    store = RunStore(cfg.data_dir)
    try:
        run_obj = store.load(run_id)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    console.print(Reporter().to_markdown(run_obj))


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host."),
    port: int = typer.Option(8000, help="Bind port."),
):
    """Launch the web dashboard."""
    from .web.server import run_server

    run_server(host=host, port=port)


@app.command()
def tui():
    """Launch the terminal UI."""
    try:
        from .tui.app import ThothansiTUI
    except ImportError:
        console.print("[red]Textual not installed. pip install textual[/red]")
        raise typer.Exit(1)
    ThothansiTUI().run()


@app.command()
def version():
    """Print version."""
    console.print(f"thothansi {__version__}")


def main():  # entry point
    app()


if __name__ == "__main__":
    main()
