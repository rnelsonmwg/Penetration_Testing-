"""
Technology fingerprinting (single low-touch HTTP request).

This is the one bundled module that contacts the target directly, but it does
no more than a browser opening the homepage: one GET, follow redirects, read
the response headers and a small slice of the body. From that it infers the
server/framework and flags missing security headers. No fuzzing, no auth
attempts, no path enumeration.
"""

from __future__ import annotations

import re

import httpx

from ..core.models import Asset, AssetType, Finding, Severity
from .base import ReconModule

# Header/body signatures -> technology label.
_SIGNATURES = {
    "server": {
        "nginx": "nginx",
        "apache": "Apache httpd",
        "cloudflare": "Cloudflare",
        "gws": "Google Web Server",
        "microsoft-iis": "Microsoft IIS",
        "envoy": "Envoy proxy",
    },
    "x-powered-by": {
        "php": "PHP",
        "express": "Express.js",
        "asp.net": "ASP.NET",
        "next.js": "Next.js",
    },
}

# Security headers and the severity assigned when absent.
_SECURITY_HEADERS = {
    "strict-transport-security": Severity.MEDIUM,
    "content-security-policy": Severity.MEDIUM,
    "x-frame-options": Severity.LOW,
    "x-content-type-options": Severity.LOW,
    "referrer-policy": Severity.INFO,
    "permissions-policy": Severity.INFO,
}


class FingerprintModule(ReconModule):
    name = "fingerprint"
    description = "Identify web tech and missing security headers via one HTTP GET."
    purely_passive = False  # sends a single request to the target

    def _execute(self, host: str) -> tuple[list[Asset], list[Finding]]:
        assets: list[Asset] = []
        findings: list[Finding] = []

        url = host if host.startswith("http") else f"https://{host}"
        headers = {"User-Agent": self.user_agent}
        try:
            with httpx.Client(
                timeout=self.timeout, follow_redirects=True, headers=headers, verify=True
            ) as client:
                resp = client.get(url)
        except Exception as e:  # pragma: no cover - network
            raise RuntimeError(f"fingerprint request failed: {e}") from e

        h = {k.lower(): v for k, v in resp.headers.items()}
        body_head = resp.text[:4096].lower() if resp.text else ""

        assets.append(
            self._asset(
                AssetType.URL,
                str(resp.url),
                status=resp.status_code,
                final_after_redirect=str(resp.url) != url,
            )
        )

        # Technology detection from headers.
        detected: list[str] = []
        for header, sigs in _SIGNATURES.items():
            val = h.get(header, "").lower()
            for needle, label in sigs.items():
                if needle in val:
                    detected.append(label)
        # A couple of body-based hints.
        if "wp-content" in body_head or "wordpress" in body_head:
            detected.append("WordPress")
        if re.search(r"<meta[^>]+generator[^>]+drupal", body_head):
            detected.append("Drupal")

        for tech in sorted(set(detected)):
            assets.append(self._asset(AssetType.TECHNOLOGY, tech, host=host))

        if detected:
            findings.append(
                Finding(
                    title="Technology fingerprint",
                    description=f"{host} appears to run: {', '.join(sorted(set(detected)))}.",
                    severity=Severity.INFO,
                    asset=host,
                    source=self.name,
                    tags=["fingerprint", "tech"],
                    evidence={"server": h.get("server", ""), "x-powered-by": h.get("x-powered-by", "")},
                )
            )

        # Missing security headers (only meaningful over https).
        if str(resp.url).startswith("https"):
            missing = [name for name in _SECURITY_HEADERS if name not in h]
            for name in missing:
                findings.append(
                    Finding(
                        title=f"Missing security header: {name}",
                        description=f"{resp.url} does not set the '{name}' response header.",
                        severity=_SECURITY_HEADERS[name],
                        asset=host,
                        source=self.name,
                        tags=["fingerprint", "headers", "hardening"],
                        evidence={"present_headers": sorted(h.keys())},
                    )
                )
        return assets, findings
