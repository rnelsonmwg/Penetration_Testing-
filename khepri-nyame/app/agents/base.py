from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models.schemas import Finding


class AgentContext(dict):
    """Shared mutable context passed between agents."""


class BaseAgent(ABC):
    name: str = "base"
    description: str = "Base agent"

    @abstractmethod
    def run(self, context: AgentContext) -> list[Finding]:
        raise NotImplementedError

    def endpoints(self, context: AgentContext) -> list[dict[str, Any]]:
        endpoints: list[dict[str, Any]] = []
        for imported in context.get("imports", []):
            endpoints.extend(imported.get("endpoints", []))
        return endpoints
