"""
Pluggable AI provider abstraction.

The whole point of Thothansi's "brain" being swappable is that offensive
methodology (what to ask) is decoupled from the model (who answers). A recon
finding is triaged the same way whether the engine behind it is a local
Ollama model or a hosted frontier model.

To add a provider, subclass :class:`AIProvider`, implement ``complete`` and
``is_available``, and register it with the ``@register`` decorator. The engine
discovers providers purely by name from config, so nothing else needs editing.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class ProviderResponse:
    text: str
    model: str
    provider: str
    raw: dict = field(default_factory=dict)


@dataclass
class ProviderConfig:
    """Normalized config passed to every provider at construction time."""

    model: str = ""
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: float = 60.0
    temperature: float = 0.2
    max_tokens: int = 1500
    extra: dict = field(default_factory=dict)


class ProviderError(RuntimeError):
    pass


class AIProvider(abc.ABC):
    """Common interface every backend implements."""

    #: Short stable identifier used in config (e.g. "ollama", "claude").
    name: str = "base"
    #: Human-friendly label.
    label: str = "Base Provider"
    #: True if the model runs on the operator's own hardware.
    local: bool = False
    #: Sensible default model if config omits one.
    default_model: str = ""

    def __init__(self, config: ProviderConfig):
        self.config = config
        if not self.config.model:
            self.config.model = self.default_model

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Cheap check: is this provider configured and reachable?"""

    @abc.abstractmethod
    def complete(self, prompt: str, system: Optional[str] = None) -> ProviderResponse:
        """Return a single completion for ``prompt`` (optionally with a system msg)."""

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        loc = "local" if self.local else "remote"
        return f"<Provider {self.name} model={self.config.model!r} {loc}>"


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
_REGISTRY: dict[str, type[AIProvider]] = {}


def register(cls: type[AIProvider]) -> type[AIProvider]:
    _REGISTRY[cls.name] = cls
    return cls


def available_providers() -> dict[str, type[AIProvider]]:
    return dict(_REGISTRY)


def get_provider(name: str, config: ProviderConfig) -> AIProvider:
    key = name.strip().lower()
    if key not in _REGISTRY:
        known = ", ".join(sorted(_REGISTRY)) or "<none>"
        raise ProviderError(f"Unknown provider {name!r}. Registered: {known}")
    return _REGISTRY[key](config)
