"""
Certificate Transparency recon via crt.sh (passive).

CT logs are a public, append-only record of issued TLS certificates. Querying
them reveals subdomains and historical hostnames without ever touching the
target. Each discovered name is re-checked against scope before being kept as
an asset, because CT logs routinely contain sibling domains you are NOT
authorized to test.
"""

from __future__ import annotations

import json

import httpx

from ..core.models import Asset, AssetType, Finding, Severity
from .base import ReconModule

CRTSH_URL = "https://crt.sh/"


class CrtShModule(ReconModule):
    name = "crtsh"
    description = "Discover subdomains & certificates from Certificate Transparency logs."
    purely_passive = True

    def _execute(self, host: str) -> tuple[list[Asset], list[Finding]]:
        assets: list[Asset] = []
        findings: list[Finding] = []

        params = {"q": f"%.{host}", "output": "json"}
        headers = {"User-Agent": self.user_agent}
        try:
            r = httpx.get(CRTSH_URL, params=params, headers=headers, timeout=self.timeout)
            r.raise_for_status()
            rows = r.json() if r.text.strip() else []
        except json.JSONDecodeError:
            rows = []
        except Exception as e:  # pragma: no cover - network
            raise RuntimeError(f"crt.sh query failed: {e}") from e

        names: set[str] = set()
        issuers: set[str] = set()
        for row in rows:
            issuers.add(row.get("issuer_name", ""))
            for name in (row.get("name_value", "") or "").splitlines():
                name = name.strip().lstrip("*.").lower()
                if name:
                    names.add(name)

        kept, dropped = 0, 0
        for name in sorted(names):
            # CRITICAL: only keep names that are themselves in authorized scope.
            if self.scope.is_in_scope(name):
                assets.append(
                    self._asset(AssetType.SUBDOMAIN, name, via="certificate-transparency")
                )
                kept += 1
            else:
                dropped += 1

        for issuer in sorted(i for i in issuers if i):
            assets.append(self._asset(AssetType.CERTIFICATE, issuer, kind="issuer"))

        if kept:
            findings.append(
                Finding(
                    title=f"{kept} subdomains via Certificate Transparency",
                    description=(
                        f"crt.sh returned {kept} in-scope hostnames for {host}"
                        + (f" ({dropped} out-of-scope names ignored)." if dropped else ".")
                    ),
                    severity=Severity.INFO,
                    asset=host,
                    source=self.name,
                    tags=["recon", "subdomains", "ct"],
                    evidence={"sample": sorted(
                        a.value for a in assets if a.type == AssetType.SUBDOMAIN
                    )[:25]},
                )
            )
        return assets, findings
