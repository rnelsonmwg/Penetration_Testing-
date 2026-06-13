from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ExperienceMode(str, Enum):
    guided_wizard = "guided_wizard"
    autonomous_agent = "autonomous_agent"
    modular_toolkit = "modular_toolkit"


class ThemeName(str, Enum):
    clean_enterprise = "clean_enterprise"
    bug_bounty_toolkit = "bug_bounty_toolkit"
    cyber_ops = "cyber_ops"


class ProviderName(str, Enum):
    local_rule_based = "local-rule-based"
    ollama = "ollama"
    openai = "openai"
    claude = "claude"
    deepseek = "deepseek"


class EngagementCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    owner: str | None = None
    mode: ExperienceMode = ExperienceMode.guided_wizard
    theme: ThemeName = ThemeName.clean_enterprise
    provider: ProviderName = ProviderName.local_rule_based
    authorization_statement: str = Field(
        min_length=12,
        description="Plain-language statement confirming authorization to test listed assets.",
    )
    scope: list[str] = Field(default_factory=list, description="Domains, CIDRs, app URLs, or API base URLs in scope.")

    @field_validator("scope")
    @classmethod
    def scope_not_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("At least one in-scope asset must be supplied.")
        return value


class Engagement(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    owner: str | None = None
    mode: ExperienceMode
    theme: ThemeName
    provider: ProviderName
    authorization_statement: str
    scope: list[str]
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    approvals: dict[str, bool] = Field(default_factory=lambda: {"active_testing": False})


class Target(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    base_url: str | None = None
    type: Literal["web", "api", "cloud", "mobile", "other"] = "api"
    notes: str | None = None


class ImportedAsset(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_type: Literal["openapi", "postman", "har", "burp", "graphql", "raw_url", "notes"]
    name: str
    raw_preview: str | None = None
    endpoints: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ApprovalRequest(BaseModel):
    active_testing: bool = False
    acknowledgement: str = Field(
        min_length=30,
        description="User must acknowledge ownership/permission, scope limits, and safe validation only.",
    )


class Finding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    severity: Literal["info", "low", "medium", "high", "critical"] = "info"
    category: str
    description: str
    evidence: list[str] = Field(default_factory=list)
    affected_assets: list[str] = Field(default_factory=list)
    safe_validation: str | None = None
    remediation: str | None = None
    confidence: Literal["low", "medium", "high"] = "medium"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class WorkflowPlan(BaseModel):
    engagement_id: str
    provider: ProviderName
    mode: ExperienceMode
    steps: list[dict[str, Any]]
    approval_required: bool = True
    safety_notes: list[str] = Field(default_factory=list)


class WorkflowRunRequest(BaseModel):
    include_active_checks: bool = False
    selected_agents: list[str] = Field(default_factory=lambda: ["recon", "api_mapper", "authz", "risk", "report"])


class ImportRequest(BaseModel):
    source_type: Literal["openapi", "postman", "har", "burp", "graphql", "raw_url", "notes"]
    name: str
    content: str


class ReportFormat(str, Enum):
    markdown = "markdown"
    html = "html"
    pdf = "pdf"
    json = "json"
    csv = "csv"
    executive = "executive"
    jira = "jira"
    github = "github"
