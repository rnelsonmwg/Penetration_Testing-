"""Shared visual themes: 'modern' (clean) and 'mythic' (gold-on-black)."""

from __future__ import annotations

THEMES = {
    "modern": {
        "label": "Modern",
        "primary": "#2563eb",
        "accent": "#0ea5e9",
        "bg": "#0f172a",
        "surface": "#1e293b",
        "text": "#e2e8f0",
        "muted": "#94a3b8",
        "critical": "#dc2626",
        "high": "#ea580c",
        "medium": "#d97706",
        "low": "#2563eb",
        "info": "#64748b",
        "rich_primary": "bright_blue",
        "rich_accent": "cyan",
        "banner_glyph": "◆",
    },
    "mythic": {
        "label": "Mythic (gold-on-black)",
        "primary": "#d4af37",
        "accent": "#c9a227",
        "bg": "#0a0a0a",
        "surface": "#161210",
        "text": "#f5e6c8",
        "muted": "#8a7a52",
        "critical": "#b91c1c",
        "high": "#c2410c",
        "medium": "#b8860b",
        "low": "#9c7a1a",
        "info": "#6b5a2e",
        "rich_primary": "gold1",
        "rich_accent": "yellow",
        "banner_glyph": "𓂀",  # Eye of Horus
    },
}


def get_theme(name: str) -> dict:
    return THEMES.get(name, THEMES["modern"])
