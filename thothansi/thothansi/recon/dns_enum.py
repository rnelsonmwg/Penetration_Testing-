"""DNS record enumeration (passive — standard resolver queries)."""

from __future__ import annotations

import dns.resolver
import dns.exception

from ..core.models import Asset, AssetType, Finding, Severity
from .base import ReconModule

_RECORD_TYPES = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "CAA"]


class DnsReconModule(ReconModule):
    name = "dns"
    description = "Resolve standard DNS records (A/AAAA/MX/NS/TXT/CNAME/SOA/CAA)."
    purely_passive = True

    def _execute(self, host: str) -> tuple[list[Asset], list[Finding]]:
        assets: list[Asset] = []
        findings: list[Finding] = []

        resolver = dns.resolver.Resolver()
        resolver.lifetime = self.timeout
        resolver.timeout = self.timeout

        records: dict[str, list[str]] = {}
        for rtype in _RECORD_TYPES:
            try:
                answers = resolver.resolve(host, rtype)
                values = [r.to_text() for r in answers]
                records[rtype] = values
                for v in values:
                    if rtype in ("A", "AAAA"):
                        assets.append(
                            self._asset(AssetType.IP, v.strip(), record=rtype, host=host)
                        )
                    assets.append(
                        self._asset(
                            AssetType.DNS_RECORD, f"{host} {rtype} {v}", rtype=rtype
                        )
                    )
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                continue
            except dns.exception.DNSException:
                continue

        # Light, non-judgmental observations useful to a hunter.
        spf = [t for t in records.get("TXT", []) if "v=spf1" in t.lower()]
        if not spf:
            findings.append(
                Finding(
                    title="No SPF record found",
                    description=f"{host} has no v=spf1 TXT record; sender policy is undefined.",
                    severity=Severity.LOW,
                    asset=host,
                    source=self.name,
                    tags=["dns", "email", "spf"],
                    evidence={"txt_records": records.get("TXT", [])},
                )
            )
        if not records.get("CAA"):
            findings.append(
                Finding(
                    title="No CAA record",
                    description=f"{host} has no CAA record restricting certificate issuance.",
                    severity=Severity.INFO,
                    asset=host,
                    source=self.name,
                    tags=["dns", "tls", "caa"],
                )
            )
        return assets, findings
