"""
Recon module framework.

Every passive-recon technique is a :class:`ReconModule`. The base class owns
the parts that must never be skipped:

  * **Scope enforcement.** ``run()`` calls ``scope.assert_in_scope`` before any
    network activity. Subclasses implement ``_execute`` and can assume the host
    is already authorized.
  * **Timing & error capture.** Results always come back as a ``ReconResult``,
    even on failure, so the pipeline never crashes on one bad target.

All bundled modules are passive: they query public data sources (DNS resolvers,
certificate transparency logs) or make a single low-touch HTTP request a normal
browser would make. None perform intrusive scanning, fuzzing, or exploitation.
"""

from __future__ import annotations

import abc
from datetime import datetime, timezone

from ..core.models import Asset, Finding, ReconResult
from ..core.scope import Scope, ScopeViolation


class ReconModule(abc.ABC):
    name: str = "base"
    description: str = ""
    #: False means the module sends traffic to the target (still low-touch).
    purely_passive: bool = True

    def __init__(self, scope: Scope, *, timeout: float = 15.0, user_agent: str = "Thothansi"):
        self.scope = scope
        self.timeout = timeout
        self.user_agent = user_agent

    def run(self, target: str) -> ReconResult:
        result = ReconResult(module=self.name, target=target)
        try:
            host = self.scope.assert_in_scope(target)
        except ScopeViolation as e:
            result.error = f"scope-refused: {e.reason}"
            result.finished_at = datetime.now(timezone.utc)
            return result

        try:
            assets, findings = self._execute(host)
            result.assets = assets
            result.findings = findings
        except Exception as e:  # pragma: no cover - module/network failures
            result.error = f"{type(e).__name__}: {e}"
        result.finished_at = datetime.now(timezone.utc)
        return result

    @abc.abstractmethod
    def _execute(self, host: str) -> tuple[list[Asset], list[Finding]]:
        """Do the actual passive recon. ``host`` is guaranteed in-scope."""

    # convenience helpers for subclasses
    def _asset(self, type_, value, **attrs) -> Asset:
        return Asset(type=type_, value=value, source=self.name, attributes=attrs)
