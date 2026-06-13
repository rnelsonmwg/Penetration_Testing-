"""
Thothansi terminal UI (Textual).

A keyboard-driven cockpit for an engagement: review the authorized scope,
add to it on the fly, enter targets, run the pipeline, and watch findings
land in the ledger. Press 't' to toggle the modern/mythic theme.

The heavy work (recon + triage) runs in a worker thread so the UI stays
responsive; events stream into the log as each module finishes.
"""

from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Log,
    Static,
)

from ..core import AppConfig, Engine, Scope, ScopeFileError
from ..core.models import RunStage

CONFIG_PATH = Path("config/config.yaml")
SCOPE_PATH = Path("config/scope.yaml")

MODERN_CSS = """
Screen { background: #0b1120; color: #e6edf7; }
#sidebar { width: 36; border: round #26344d; padding: 1; }
#main { padding: 1; }
.title { color: #4f8cff; text-style: bold; }
#scopelist { height: 12; border: round #26344d; }
Button { background: #4f8cff; color: #0b1120; }
Button.secondary { background: #1b263c; color: #e6edf7; }
#log { height: 10; border: round #26344d; background: #0b1120; }
DataTable { height: 1fr; border: round #26344d; }
.crit { color: #f0506e; } .high { color: #ff8a4c; } .med { color: #f5c451; }
"""

MYTHIC_CSS = """
Screen { background: #0a0805; color: #f3e6c4; }
#sidebar { width: 36; border: round #3a2f18; padding: 1; }
#main { padding: 1; }
.title { color: #d4af37; text-style: bold; }
#scopelist { height: 12; border: round #3a2f18; }
Button { background: #d4af37; color: #0a0805; }
Button.secondary { background: #1e1810; color: #f3e6c4; }
#log { height: 10; border: round #3a2f18; background: #0a0805; }
DataTable { height: 1fr; border: round #3a2f18; }
.crit { color: #c1452f; } .high { color: #c9772a; } .med { color: #c9a227; }
"""


class ThothansiTUI(App):
    TITLE = "Thothansi"
    SUB_TITLE = "the weaver & the scribe"
    CSS = MODERN_CSS
    BINDINGS = [
        ("t", "toggle_theme", "Toggle theme"),
        ("r", "focus_targets", "Targets"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.config = AppConfig.load(CONFIG_PATH if CONFIG_PATH.exists() else None)
        self._scope_error = ""
        try:
            self.scope = (
                Scope.from_file(SCOPE_PATH) if SCOPE_PATH.exists() else Scope("unconfigured")
            )
        except ScopeFileError as e:
            self.scope = Scope("unconfigured")
            self._scope_error = e.message
        self._theme_name = self.config.theme

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Label("SCOPE", classes="title")
                yield Static(self.scope.engagement, id="engagement")
                yield VerticalScroll(Static(self._scope_text(), id="scopelist"))
                yield Input(placeholder="add to scope…", id="scopeinput")
                yield Label("PROVIDER", classes="title")
                yield Static(self._provider_text(), id="providers")
            with Vertical(id="main"):
                yield Label("TARGETS (comma or space separated)", classes="title")
                yield Input(placeholder="example.com api.example.com", id="targets")
                with Horizontal():
                    yield Button("Weave ▸", id="run", variant="primary")
                    yield Button("Toggle triage: ON", id="triage", classes="secondary")
                yield Log(id="log", highlight=True)
                yield DataTable(id="findings")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#findings", DataTable)
        table.add_columns("Severity", "Title", "Asset", "Source")
        self._apply_theme()
        self._do_triage = True
        if self._scope_error:
            self.notify(self._scope_error, title="Scope file error", severity="error", timeout=10)

    # ---- helpers -------------------------------------------------------------
    def _scope_text(self) -> str:
        if self.scope.is_empty:
            return "[dim]empty — add targets[/dim]"
        return "\n".join(f"🕸 {e}" for e in self.scope.entries)

    def _provider_text(self) -> str:
        lines = []
        for p in self.config.provider_status():
            mark = "●" if p["configured"] else "○"
            active = " *" if p["active"] else ""
            lines.append(f"{mark} {p['label']}{active}")
        return "\n".join(lines)

    def _apply_theme(self) -> None:
        self.app.stylesheet  # noqa
        self.CSS = MYTHIC_CSS if self._theme_name == "mythic" else MODERN_CSS
        self.refresh_css()

    # ---- actions -------------------------------------------------------------
    def action_toggle_theme(self) -> None:
        self._theme_name = "mythic" if self._theme_name == "modern" else "modern"
        self._apply_theme()
        self.notify(f"Theme: {self._theme_name}")

    def action_focus_targets(self) -> None:
        self.query_one("#targets", Input).focus()

    @on(Button.Pressed, "#triage")
    def toggle_triage(self, event: Button.Pressed) -> None:
        self._do_triage = not getattr(self, "_do_triage", True)
        event.button.label = f"Toggle triage: {'ON' if self._do_triage else 'OFF'}"

    @on(Input.Submitted, "#scopeinput")
    def add_scope(self, event: Input.Submitted) -> None:
        val = event.value.strip()
        if val:
            self.scope.add(val)
            if SCOPE_PATH.exists():
                self.scope.save(SCOPE_PATH)
            self.query_one("#scopelist", Static).update(self._scope_text())
            event.input.value = ""
            self.notify(f"Added to scope: {val}")

    @on(Button.Pressed, "#run")
    def start_run(self) -> None:
        raw = self.query_one("#targets", Input).value
        targets = [t for t in raw.replace(",", " ").split() if t]
        if not targets:
            self.notify("Enter at least one target", severity="warning")
            return
        log = self.query_one("#log", Log)
        log.clear()
        self.query_one("#findings", DataTable).clear()
        self.run_pipeline_worker(targets)

    @work(thread=True)
    def run_pipeline_worker(self, targets: list[str]) -> None:
        log = self.query_one("#log", Log)

        def emit(stage: str, msg: str) -> None:
            self.call_from_thread(log.write_line, f"[{stage}] {msg}")

        engine = Engine(self.config, self.scope, on_event=emit)
        run = engine.run_pipeline(targets, interactive=False, do_triage=self._do_triage)
        self.call_from_thread(self._populate_findings, run)

    def _populate_findings(self, run) -> None:
        table = self.query_one("#findings", DataTable)
        table.clear()
        for f in run.all_findings():
            sev = f.effective_severity.value
            table.add_row(sev, f.title, f.asset or "-", f.source)
        self.notify(f"Run {run.id}: {len(run.all_findings())} findings")
