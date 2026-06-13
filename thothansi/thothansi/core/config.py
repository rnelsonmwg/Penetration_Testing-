"""
Configuration loading.

Config comes from two layers, lowest priority first:
  1. A YAML config file (``config/config.yaml``).
  2. Environment variables (for secrets, especially API keys).

Secrets should live in the environment / ``.env``, never in the YAML that
gets committed. Each provider declares which env var holds its key; the loader
wires that up so the YAML only needs to name the active provider and model.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field

from ..providers import ProviderConfig, available_providers

# Maps provider name -> env var that holds its API key.
_KEY_ENV = {
    "claude": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "groq": "GROQ_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "grok": "XAI_API_KEY",
    "ollama": "",  # no key
}


class ReconConfig(BaseModel):
    enabled_modules: list[str] = Field(
        default_factory=lambda: ["dns", "crtsh", "subdomains", "fingerprint"]
    )
    request_timeout: float = 15.0
    max_concurrency: int = 8
    # Passive-by-default: never send active/intrusive traffic.
    passive_only: bool = True
    user_agent: str = "Thothansi/0.1 (+authorized-recon)"


class AppConfig(BaseModel):
    active_provider: str = "ollama"
    provider_model: Optional[str] = None
    provider_base_url: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 1500

    theme: str = "modern"  # "modern" | "mythic"
    interactive: bool = False  # step-gated pipeline if True

    recon: ReconConfig = Field(default_factory=ReconConfig)

    data_dir: str = "./thothansi-data"

    # ---- loading -------------------------------------------------------------
    @classmethod
    def load(cls, path: str | Path | None = None) -> "AppConfig":
        data: dict = {}
        if path:
            p = Path(path)
            if p.exists():
                data = yaml.safe_load(p.read_text()) or {}
        cfg = cls(**data)
        # Environment overrides for a few common knobs.
        cfg.active_provider = os.getenv("THOTHANSI_PROVIDER", cfg.active_provider)
        if os.getenv("THOTHANSI_MODEL"):
            cfg.provider_model = os.getenv("THOTHANSI_MODEL")
        if os.getenv("THOTHANSI_THEME"):
            cfg.theme = os.getenv("THOTHANSI_THEME")
        if os.getenv("THOTHANSI_BASE_URL"):
            cfg.provider_base_url = os.getenv("THOTHANSI_BASE_URL")
        return cfg

    # ---- provider wiring -----------------------------------------------------
    def provider_config(self, provider: Optional[str] = None) -> ProviderConfig:
        name = (provider or self.active_provider).lower()
        env_key = _KEY_ENV.get(name, "")
        api_key = os.getenv(env_key) if env_key else None
        return ProviderConfig(
            model=self.provider_model or "",
            api_key=api_key,
            base_url=self.provider_base_url,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    def provider_status(self) -> list[dict]:
        """Report which providers are configured/available (for the dashboard)."""
        out = []
        for name, cls in sorted(available_providers().items()):
            inst = cls(self.provider_config(name))
            out.append(
                {
                    "name": name,
                    "label": cls.label,
                    "local": cls.local,
                    "model": inst.config.model,
                    "configured": inst.is_available() if cls.local else bool(inst.config.api_key),
                    "active": name == self.active_provider,
                }
            )
        return out
