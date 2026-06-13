"""
Passive subdomain aggregation.

Pulls hostnames from free, keyless public sources and merges them. This
complements the CT-log module with passive-DNS style data. Every candidate is
scope-filtered before it is kept. Sources are queried defensively: one failing
source never aborts the others.

Add your own sources by appending to ``SOURCES`` — each is a callable that
takes (host, http_client) and yields hostnames.
"""

from __future__ import annotations

from typing import Callable, Iterable

import httpx

from ..core.models import Asset, AssetType, Finding, Severity
from .base import ReconModule


def _hackertarget(host: str, client: httpx.Client) -> Iterable[str]:
    """api.hackertarget.com hostsearch returns 'hostname,ip' CSV lines."""
    r = client.get("https://api.hackertarget.com/hostsearch/", params={"q": host})
    if r.status_code != 200 or "error" in r.text.lower():
        return []
    out = []
    for line in r.text.splitlines():
        name = line.split(",", 1)[0].strip().lower()
        if name:
            out.append(name)
    return out


def _certspotter(host: str, client: httpx.Client) -> Iterable[str]:
    """Cert Spotter issuances API (keyless tier)."""
    r = client.get(
        "https://api.certspotter.com/v1/issuances",
        params={"domain": host, "include_subdomains": "true", "expand": "dns_names"},
    )
    if r.status_code != 200:
        return []
    names: set[str] = set()
    for entry in r.json():
        for n in entry.get("dns_names", []):
            names.add(n.strip().lstrip("*.").lower())
    return names


SOURCES: list[Callable[[str, httpx.Client], Iterable[str]]] = [
    _hackertarget,
    _certspotter,
]


class SubdomainModule(ReconModule):
    name = "subdomains"
    description = "Aggregate subdomains from free passive-DNS / CT sources."
    purely_passive = True

    def _execute(self, host: str) -> tuple[list[Asset], list[Finding]]:
        assets: list[Asset] = []
        findings: list[Finding] = []
        headers = {"User-Agent": self.user_agent}
        found: set[str] = set()
        source_errors: list[str] = []

        with httpx.Client(timeout=self.timeout, headers=headers) as client:
            for source in SOURCES:
                try:
                    for name in source(host, client):
                        found.add(name)
                except Exception as e:  # one bad source must not abort the rest
                    source_errors.append(f"{source.__name__}: {e}")

        kept = 0
        for name in sorted(found):
            if self.scope.is_in_scope(name):
                assets.append(self._asset(AssetType.SUBDOMAIN, name, via="passive-dns"))
                kept += 1

        if kept:
            findings.append(
                Finding(
                    title=f"{kept} subdomains via passive sources",
                    description=f"Aggregated {kept} in-scope subdomains for {host}.",
                    severity=Severity.INFO,
                    asset=host,
                    source=self.name,
                    tags=["recon", "subdomains", "passive-dns"],
                    evidence={
                        "sample": [a.value for a in assets][:25],
                        "source_errors": source_errors,
                    },
                )
            )
        return assets, findings
