from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.agents.base import AgentContext
from app.agents.orchestrator import run_agents
from app.ai.providers import get_provider
from app.core.config import settings
from app.models.schemas import (
    ApprovalRequest,
    Engagement,
    EngagementCreate,
    ImportRequest,
    ImportedAsset,
    ReportFormat,
    WorkflowRunRequest,
)
from app.parsers.input_parsers import parse_import
from app.reporting.exporters import export_report
from app.storage.json_store import JsonStore

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
store = JsonStore(settings.storage_dir)

app = FastAPI(
    title="Khepri Nyame",
    version="0.1.0",
    description="Local-first AI-assisted bug hunting and API security testing with human approval gates.",
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@app.get("/themes")
def themes() -> dict[str, Any]:
    return {
        "clean_enterprise": {"palette": "desert sand / obsidian", "description": "Quiet enterprise security workspace."},
        "bug_bounty_toolkit": {"palette": "green / bronze", "description": "Researcher-centric hacker toolkit."},
        "cyber_ops": {"palette": "deep blue / gold", "description": "Dark/light cyber operations console."},
    }


@app.post("/engagements", response_model=Engagement)
def create_engagement(payload: EngagementCreate) -> Engagement:
    engagement = Engagement(**payload.model_dump())
    data = engagement.model_dump()
    data.setdefault("targets", [])
    data.setdefault("imports", [])
    data.setdefault("findings", [])
    data.setdefault("plans", [])
    store.save("engagements", engagement.id, data)
    return engagement


@app.get("/engagements")
def list_engagements() -> list[dict[str, Any]]:
    return store.list("engagements")


@app.get("/engagements/{engagement_id}")
def get_engagement(engagement_id: str) -> dict[str, Any]:
    try:
        return store.load("engagements", engagement_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/engagements/{engagement_id}/imports", response_model=ImportedAsset)
def import_asset(engagement_id: str, payload: ImportRequest) -> ImportedAsset:
    engagement = get_engagement(engagement_id)
    try:
        endpoints, metadata = parse_import(payload.source_type, payload.content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Import parser failed: {exc}") from exc
    imported = ImportedAsset(
        source_type=payload.source_type,
        name=payload.name,
        raw_preview=payload.content[:50000],
        endpoints=endpoints,
        metadata=metadata,
    )
    engagement.setdefault("imports", []).append(imported.model_dump())
    store.save("engagements", engagement_id, engagement)
    return imported


@app.post("/engagements/{engagement_id}/plan")
async def create_plan(engagement_id: str) -> dict[str, Any]:
    engagement = get_engagement(engagement_id)
    provider = get_provider(engagement.get("provider", settings.default_provider))
    plan = await provider.generate_plan(engagement, engagement.get("imports", []))
    engagement.setdefault("plans", []).append(plan.model_dump())
    store.save("engagements", engagement_id, engagement)
    return plan.model_dump()


@app.post("/engagements/{engagement_id}/approval")
def set_approval(engagement_id: str, payload: ApprovalRequest) -> dict[str, Any]:
    engagement = get_engagement(engagement_id)
    # The MVP still only runs passive/safe analysis. This flag exists so later
    # active checks can be added without changing the approval model.
    engagement.setdefault("approvals", {})["active_testing"] = bool(payload.active_testing)
    engagement["approval_acknowledgement"] = payload.acknowledgement
    store.save("engagements", engagement_id, engagement)
    return {"active_testing": engagement["approvals"]["active_testing"], "message": "Approval preference saved. Safe boundaries remain enforced."}


@app.post("/engagements/{engagement_id}/run")
def run_workflow(engagement_id: str, payload: WorkflowRunRequest) -> dict[str, Any]:
    engagement = get_engagement(engagement_id)
    if payload.include_active_checks and not engagement.get("approvals", {}).get("active_testing", False):
        raise HTTPException(status_code=403, detail="Active checks requested but human approval has not been recorded.")
    context = AgentContext(engagement=engagement, imports=engagement.get("imports", []), findings=engagement.get("findings", []))
    selected = payload.selected_agents or None
    findings = run_agents(context, selected)
    engagement["findings"] = context.get("findings", [])
    store.save("engagements", engagement_id, engagement)
    return {"engagement_id": engagement_id, "new_findings": [f.model_dump() for f in findings], "total_findings": len(engagement["findings"])}


@app.get("/engagements/{engagement_id}/report/{fmt}")
def get_report(engagement_id: str, fmt: ReportFormat) -> Response:
    engagement = get_engagement(engagement_id)
    content, media_type, extension = export_report(engagement, fmt.value)
    filename = f"khepri-nyame-{engagement_id}.{extension}"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return Response(content=content, media_type=media_type, headers=headers)
