"""Recon module registry."""

from __future__ import annotations

from .base import ReconModule
from .crtsh import CrtShModule
from .dns_enum import DnsReconModule
from .fingerprint import FingerprintModule
from .subdomains import SubdomainModule

MODULES: dict[str, type[ReconModule]] = {
    DnsReconModule.name: DnsReconModule,
    CrtShModule.name: CrtShModule,
    SubdomainModule.name: SubdomainModule,
    FingerprintModule.name: FingerprintModule,
}


def get_modules(names: list[str]) -> list[type[ReconModule]]:
    out = []
    for n in names:
        if n in MODULES:
            out.append(MODULES[n])
    return out


__all__ = ["MODULES", "get_modules", "ReconModule"]
