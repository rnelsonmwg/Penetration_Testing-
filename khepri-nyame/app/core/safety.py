from __future__ import annotations

import re
from urllib.parse import urlparse

BLOCKED_ACTION_KEYWORDS = {
    "bruteforce",
    "brute force",
    "password spray",
    "credential stuffing",
    "persistence",
    "lateral movement",
    "exfiltrate",
    "data extraction",
    "stealth",
    "evasion",
    "destructive",
    "dropper",
    "ransomware",
}


def assert_authorized_scope(scope: list[str], target: str) -> bool:
    """Return True if target appears to be inside one of the engagement scope entries.

    This is a conservative guardrail, not a replacement for legal authorization.
    """
    if not target:
        return False
    normalized_target = normalize_asset(target)
    for item in scope:
        normalized_scope = normalize_asset(item)
        if normalized_target == normalized_scope or normalized_target.endswith("." + normalized_scope):
            return True
        if normalized_scope in normalized_target:
            return True
    return False


def normalize_asset(asset: str) -> str:
    asset = asset.strip().lower()
    parsed = urlparse(asset if "://" in asset else f"https://{asset}")
    host = parsed.netloc or parsed.path
    return host.split(":")[0].strip("/")


def validate_workflow_name(name: str) -> None:
    lowered = name.lower()
    for keyword in BLOCKED_ACTION_KEYWORDS:
        if keyword in lowered:
            raise ValueError(f"Blocked unsafe workflow keyword: {keyword}")


def redact_secret(value: str) -> str:
    if len(value) <= 8:
        return "[REDACTED]"
    return value[:4] + "...[REDACTED]..." + value[-4:]


SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd|pwd)\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]{12,})"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)bearer\s+([A-Za-z0-9_\-\.]{20,})"),
]


def find_possible_secrets(text: str) -> list[str]:
    results: list[str] = []
    for pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            secret = match.group(0)
            results.append(redact_secret(secret))
    return sorted(set(results))
