"""
Web dashboard backend (FastAPI).

Exposes a small JSON API plus the static single-page dashboard:

  GET  /api/state            config summary + provider status + theme
  GET  /api/scope            current authorized scope
  POST /api/scope            add an entry to scope (dynamic, audited)
  GET  /api/runs             list saved runs
  GET  /api/runs/{id}        full run detail
  POST /api/run              start a pipeline run (in-scope targets only)
  GET  /api/report/{id}      Markdown report for a run

The server enforces scope exactly like the CLI: out-of-scope targets are
refused by the engine, never silently dropped.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..core import AppConfig, Engine, Scope, ScopeFileError
from ..core.store import RunStore
from ..report import Reporter
from ..theme import THEMES, get_theme

STATIC_DIR = Path(__file__).parent / "static"
CONFIG_PATH = Path("config/config.yaml")
SCOPE_PATH = Path("config/scope.yaml")


def _config() -> AppConfig:
    return AppConfig.load(CONFIG_PATH if CONFIG_PATH.exists() else None)


def _scope() -> Scope:
    if SCOPE_PATH.exists():
        return Scope.from_file(SCOPE_PATH)
    return Scope("unconfigured")


class ScopeAddBody(BaseModel):
    value: str
    note: str = ""


class RunBody(BaseModel):
    targets: list[str]
    interactive: bool = False
    do_triage: bool = True
    provider: Optional[str] = None


def create_app() -> FastAPI:
    api = FastAPI(title="Thothansi", version="0.1.0")

    @api.exception_handler(ScopeFileError)
    def _scope_file_error(_request, exc: ScopeFileError):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=400,
            content={"error": exc.message, "hint": exc.hint},
        )

    @api.get("/api/state")
    def state():
        cfg = _config()
        return {
            "version": "0.1.0",
            "theme": cfg.theme,
            "themes": {k: v["label"] for k, v in THEMES.items()},
            "active_provider": cfg.active_provider,
            "providers": cfg.provider_status(),
            "interactive_default": cfg.interactive,
            "modules": cfg.recon.enabled_modules,
        }

    @api.get("/api/theme/{name}")
    def theme(name: str):
        return get_theme(name)

    @api.get("/api/scope")
    def get_scope():
        s = _scope()
        return {
            "engagement": s.engagement,
            "authorized_by": s.authorized_by,
            "entries": s.entries,
            "empty": s.is_empty,
        }

    @api.post("/api/scope")
    def add_scope(body: ScopeAddBody):
        s = _scope()
        s.add(body.value, note=body.note)
        if SCOPE_PATH.exists():
            s.save(SCOPE_PATH)
        return {"ok": True, "entries": s.entries}

    @api.get("/api/runs")
    def list_runs():
        cfg = _config()
        return RunStore(cfg.data_dir).list_runs()

    @api.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        cfg = _config()
        try:
            run = RunStore(cfg.data_dir).load(run_id)
        except FileNotFoundError:
            raise HTTPException(404, "run not found")
        return {
            "id": run.id,
            "targets": run.targets,
            "severity_counts": run.severity_counts(),
            "asset_counts": run.asset_counts(),
            "findings": [f.model_dump(mode="json") for f in run.all_findings()],
            "assets": [a.model_dump(mode="json") for a in run.all_assets()],
        }

    @api.get("/api/report/{run_id}", response_class=PlainTextResponse)
    def report(run_id: str):
        cfg = _config()
        try:
            run = RunStore(cfg.data_dir).load(run_id)
        except FileNotFoundError:
            raise HTTPException(404, "run not found")
        return Reporter().to_markdown(run)

    @api.post("/api/run")
    def start_run(body: RunBody):
        cfg = _config()
        if body.provider:
            cfg.active_provider = body.provider
        scope = _scope()
        allowed, refused = scope.filter_in_scope(body.targets)
        if not allowed:
            raise HTTPException(
                400,
                detail={"error": "no in-scope targets", "refused": refused},
            )
        events: list[dict] = []
        engine = Engine(
            cfg, scope, on_event=lambda stage, msg: events.append({"stage": stage, "msg": msg})
        )
        run = engine.run_pipeline(
            allowed, interactive=False, do_triage=body.do_triage
        )
        return {
            "run_id": run.id,
            "refused": refused,
            "events": events,
            "severity_counts": run.severity_counts(),
            "asset_counts": run.asset_counts(),
            "findings": [f.model_dump(mode="json") for f in run.all_findings()],
        }

    if STATIC_DIR.exists():
        api.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return api


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run(create_app(), host=host, port=port)
