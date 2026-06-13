"""
Scope & authorization layer.

This is the single most important module in Thothansi from a safety and
legal standpoint. Every recon module must consult the active ``Scope`` before
touching a target. Anything not explicitly declared in scope is refused.

Design principles:
  * Default-deny. An empty scope authorizes nothing.
  * Explicit allow-list of domains (with optional wildcards) and IP networks.
  * Optional out-of-scope deny-list that overrides allows (e.g. a corp WAF,
    a shared-hosting neighbour, a third-party asset you must not test).
  * Dynamic additions are supported at runtime (the TUI/web "add to scope"
    box) but every addition is recorded with a timestamp for the audit log.

The scope file is YAML so a human can read and review it before a run.
"""

from __future__ import annotations

import ipaddress
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class ScopeViolation(Exception):
    """Raised (or surfaced) when an out-of-scope target is requested."""

    def __init__(self, target: str, reason: str = "not in authorized scope"):
        self.target = target
        self.reason = reason
        super().__init__(f"Refusing '{target}': {reason}")


class ScopeFileError(Exception):
    """Raised when a scope file is missing, malformed, or has the wrong shape.

    Carries a human-readable ``message`` (safe to show a user without a
    traceback) and, when available, the underlying parser detail and a hint.
    """

    def __init__(self, message: str, hint: str = "", detail: str = ""):
        self.message = message
        self.hint = hint
        self.detail = detail
        super().__init__(message)


class ScopeEntry(BaseModel):
    value: str
    note: str = ""
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def _normalize_host(target: str) -> str:
    """Strip scheme, path, port, and lowercase a host-like target."""
    t = target.strip().lower()
    t = re.sub(r"^[a-z][a-z0-9+.\-]*://", "", t)  # scheme
    t = t.split("/", 1)[0]  # path
    t = t.split("@")[-1]  # userinfo
    # strip :port but keep IPv6 brackets intact
    if t.startswith("["):
        return t  # leave IPv6 literal handling to caller
    t = t.split(":", 1)[0]
    return t.rstrip(".")


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


class Scope:
    """Holds the authorized testing boundary and enforces it."""

    def __init__(
        self,
        engagement: str = "unnamed-engagement",
        authorized_by: str = "",
    ) -> None:
        self.engagement = engagement
        self.authorized_by = authorized_by
        self._domains: list[ScopeEntry] = []
        self._networks: list[tuple[ipaddress._BaseNetwork, ScopeEntry]] = []
        self._out_domains: list[str] = []
        self._out_networks: list[ipaddress._BaseNetwork] = []
        self.audit_log: list[str] = []

    # ---- construction --------------------------------------------------------
    @classmethod
    def from_file(cls, path: str | Path) -> "Scope":
        path = Path(path)
        if not path.exists():
            raise ScopeFileError(
                f"No scope file at {path}.",
                hint="Run 'thothansi init' to create one, then add your authorized targets.",
            )

        text = path.read_text()
        try:
            data = yaml.safe_load(text) or {}
        except yaml.YAMLError as e:
            mark = getattr(e, "problem_mark", None)
            where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
            raise ScopeFileError(
                f"Could not parse {path}{where}: the YAML is malformed.",
                hint=(
                    "Check indentation — keys inside a list item must line up under "
                    "the first key after the dash, e.g.\n"
                    '    in_scope:\n'
                    '      - value: "example.com"\n'
                    '        note: "primary target"   # aligned under "value", not the dash'
                ),
                detail=str(e),
            ) from None

        if not isinstance(data, dict):
            raise ScopeFileError(
                f"{path} must contain a YAML mapping with keys like "
                "'engagement', 'in_scope', and 'out_of_scope'.",
                hint="See config/scope.example.yaml for the expected structure.",
            )

        scope = cls(
            engagement=data.get("engagement", "unnamed-engagement"),
            authorized_by=data.get("authorized_by", ""),
        )
        scope._load_entries(data.get("in_scope"), path, "in_scope", scope.add)
        scope._load_entries(
            data.get("out_of_scope"), path, "out_of_scope",
            lambda v, note="", audit=False: scope.add_out_of_scope(v),
        )
        return scope

    def _load_entries(self, items, path, key, adder) -> None:
        if items is None:
            return
        if not isinstance(items, list):
            raise ScopeFileError(
                f"'{key}' in {path} must be a list, got {type(items).__name__}.",
                hint="Each entry should be a '- value: ...' list item.",
            )
        for item in items:
            value, note = self._split_item(item)
            if not value:
                raise ScopeFileError(
                    f"An entry under '{key}' in {path} has no 'value'.",
                    hint='Use either  - "example.com"  or  - value: "example.com".',
                )
            adder(value, note=note, audit=False)

    @staticmethod
    def _split_item(item) -> tuple[str, str]:
        if isinstance(item, dict):
            return str(item.get("value", "")), str(item.get("note", ""))
        return str(item), ""

    def to_dict(self) -> dict:
        return {
            "engagement": self.engagement,
            "authorized_by": self.authorized_by,
            "in_scope": [e.value for e in self._domains]
            + [e.value for _, e in self._networks],
            "out_of_scope": list(self._out_domains)
            + [str(n) for n in self._out_networks],
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(yaml.safe_dump(self.to_dict(), sort_keys=False))

    # ---- mutation ------------------------------------------------------------
    def add(self, value: str, note: str = "", audit: bool = True) -> ScopeEntry:
        """Add a domain (optionally wildcard) or IP/CIDR to the allow-list."""
        value = value.strip().lower()
        entry = ScopeEntry(value=value, note=note)
        try:
            net = ipaddress.ip_network(value, strict=False)
            self._networks.append((net, entry))
        except ValueError:
            self._domains.append(entry)
        if audit:
            self.audit_log.append(
                f"{entry.added_at.isoformat()}  ADD-SCOPE  {value}"
                + (f"  ({note})" if note else "")
            )
        return entry

    def add_out_of_scope(self, value: str) -> None:
        value = value.strip().lower()
        try:
            self._out_networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            self._out_domains.append(value)

    # ---- enforcement ---------------------------------------------------------
    def _matches_domain(self, host: str, pattern: str) -> bool:
        """Match host against a domain pattern.

        ``example.com``    matches example.com and any subdomain.
        ``*.example.com``  matches subdomains only (not the apex).
        ``api.example.com``matches exactly that host and its subdomains.
        """
        if pattern.startswith("*."):
            base = pattern[2:]
            # Wildcard matches subdomains only; the apex is excluded.
            return host.endswith("." + base)
        return host == pattern or host.endswith("." + pattern)

    def is_in_scope(self, target: str) -> bool:
        host = _normalize_host(target)
        if not host:
            return False

        # Deny-list overrides everything.
        if _is_ip(host):
            ip = ipaddress.ip_address(host)
            if any(ip in n for n in self._out_networks):
                return False
        else:
            if any(self._matches_domain(host, p) for p in self._out_domains):
                return False

        # Allow-list.
        if _is_ip(host):
            ip = ipaddress.ip_address(host)
            return any(ip in net for net, _ in self._networks)
        return any(self._matches_domain(host, e.value) for e in self._domains)

    def assert_in_scope(self, target: str) -> str:
        """Return the normalized host if in scope, else raise ScopeViolation."""
        if not self.is_in_scope(target):
            raise ScopeViolation(target)
        return _normalize_host(target)

    def filter_in_scope(self, targets: list[str]) -> tuple[list[str], list[str]]:
        """Split a list into (allowed, refused)."""
        allowed, refused = [], []
        for t in targets:
            (allowed if self.is_in_scope(t) else refused).append(t)
        return allowed, refused

    # ---- introspection -------------------------------------------------------
    @property
    def entries(self) -> list[str]:
        return [e.value for e in self._domains] + [e.value for _, e in self._networks]

    @property
    def is_empty(self) -> bool:
        return not self._domains and not self._networks

    def summary(self) -> str:
        return (
            f"engagement={self.engagement!r} "
            f"domains={len(self._domains)} networks={len(self._networks)} "
            f"out_of_scope={len(self._out_domains) + len(self._out_networks)}"
        )
