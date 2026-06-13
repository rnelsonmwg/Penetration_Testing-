"""
Thothansi core data models.

These Pydantic models are the shared vocabulary across recon, triage,
reporting, and the interfaces (CLI / TUI / web). Keeping them in one place
means a finding produced by a recon module looks identical whether it is
rendered in the terminal, scored by an AI provider, or written to a report.
"""

from __future__ import annotations

import enum
import hashlib
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Severity(str, enum.Enum):
    """Qualitative severity bands used for triage and prioritization."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        order = {
            "info": 0,
            "low": 1,
            "medium": 2,
            "high": 3,
            "critical": 4,
        }
        return order[self.value]


class AssetType(str, enum.Enum):
    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    IP = "ip"
    URL = "url"
    DNS_RECORD = "dns_record"
    CERTIFICATE = "certificate"
    SERVICE = "service"
    TECHNOLOGY = "technology"


class Asset(BaseModel):
    """A single discovered piece of attack surface.

    Assets are intentionally lightweight and additive: recon modules append
    assets, and de-duplication happens by (type, value).
    """

    type: AssetType
    value: str
    source: str = Field(description="Which recon module produced this asset")
    attributes: dict[str, Any] = Field(default_factory=dict)
    discovered_at: datetime = Field(default_factory=_utcnow)

    @property
    def key(self) -> str:
        return f"{self.type.value}:{self.value.lower()}"


class Finding(BaseModel):
    """A noteworthy observation that may warrant follow-up.

    Findings are produced by recon modules (e.g. an interesting header, an
    exposed development subdomain) and are the unit that AI triage scores.
    """

    id: str = ""
    title: str
    description: str = ""
    severity: Severity = Severity.INFO
    asset: Optional[str] = None
    source: str = "thothansi"
    tags: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)

    # Filled in by the AI triage stage.
    triage_severity: Optional[Severity] = None
    triage_rationale: Optional[str] = None
    triage_recommendation: Optional[str] = None
    triage_confidence: Optional[float] = None

    created_at: datetime = Field(default_factory=_utcnow)

    def model_post_init(self, __context: Any) -> None:  # noqa: D401
        if not self.id:
            basis = f"{self.title}|{self.asset}|{self.source}"
            self.id = hashlib.sha1(basis.encode()).hexdigest()[:12]

    @property
    def effective_severity(self) -> Severity:
        """Triage severity wins once triage has run, else the raw severity."""
        return self.triage_severity or self.severity


class ReconResult(BaseModel):
    """The output of one recon module run against one target."""

    module: str
    target: str
    assets: list[Asset] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=_utcnow)
    finished_at: Optional[datetime] = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


class RunStage(str, enum.Enum):
    RECON = "recon"
    TRIAGE = "triage"
    REPORT = "report"


class Run(BaseModel):
    """A full pipeline execution: recon -> triage -> report."""

    id: str = Field(default_factory=lambda: _utcnow().strftime("run-%Y%m%d-%H%M%S"))
    targets: list[str] = Field(default_factory=list)
    results: list[ReconResult] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=_utcnow)
    finished_at: Optional[datetime] = None

    # ---- aggregation helpers -------------------------------------------------
    def all_assets(self) -> list[Asset]:
        seen: dict[str, Asset] = {}
        for r in self.results:
            for a in r.assets:
                seen.setdefault(a.key, a)
        return list(seen.values())

    def all_findings(self) -> list[Finding]:
        seen: dict[str, Finding] = {}
        for r in self.results:
            for f in r.findings:
                seen.setdefault(f.id, f)
        return sorted(
            seen.values(),
            key=lambda f: f.effective_severity.rank,
            reverse=True,
        )

    def asset_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for a in self.all_assets():
            counts[a.type.value] = counts.get(a.type.value, 0) + 1
        return counts

    def severity_counts(self) -> dict[str, int]:
        counts = {s.value: 0 for s in Severity}
        for f in self.all_findings():
            counts[f.effective_severity.value] += 1
        return counts
