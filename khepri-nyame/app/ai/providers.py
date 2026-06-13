from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import settings
from app.models.schemas import ProviderName, WorkflowPlan


class AIProvider(ABC):
    name: ProviderName

    @abstractmethod
    async def generate_plan(self, engagement: dict[str, Any], imports: list[dict[str, Any]]) -> WorkflowPlan:
        raise NotImplementedError


class LocalRuleBasedProvider(AIProvider):
    name = ProviderName.local_rule_based

    async def generate_plan(self, engagement: dict[str, Any], imports: list[dict[str, Any]]) -> WorkflowPlan:
        endpoint_count = sum(len(item.get("endpoints", [])) for item in imports)
        steps = [
            {"agent": "recon", "goal": "Build passive attack-surface inventory from imported sources.", "active": False},
            {"agent": "api_mapper", "goal": "Map API routes, methods, identifiers, and sensitive business workflows.", "active": False},
            {"agent": "secret_review", "goal": "Check imported artifacts for redacted potential secret exposure.", "active": False},
            {"agent": "authz", "goal": "Prioritize BOLA/BFLA, SSRF/open redirect, injection, CORS, rate-limit, GraphQL, and mass-assignment review candidates.", "active": False},
            {"agent": "risk", "goal": "Rank candidate issues by severity, confidence, and validation priority.", "active": False},
            {"agent": "report", "goal": "Generate technical and executive report artifacts.", "active": False},
        ]
        if endpoint_count == 0:
            steps.insert(0, {"agent": "import", "goal": "Import OpenAPI, Postman, HAR, Burp, raw URLs, or GraphQL schema before analysis.", "active": False})
        return WorkflowPlan(
            engagement_id=engagement["id"],
            provider=self.name,
            mode=engagement.get("mode", "guided_wizard"),
            steps=steps,
            approval_required=True,
            safety_notes=[
                "First release avoids exploit execution and credential attacks.",
                "Active checks require explicit human approval and must stay inside engagement scope.",
                "Generated payloads are framed as safe validation guidance, not automated exploitation.",
            ],
        )


class OllamaProvider(LocalRuleBasedProvider):
    name = ProviderName.ollama

    async def generate_plan(self, engagement: dict[str, Any], imports: list[dict[str, Any]]) -> WorkflowPlan:
        prompt = _planning_prompt(engagement, imports)
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    f"{settings.ollama_base_url.rstrip('/')}/api/generate",
                    json={"model": os.getenv("OLLAMA_MODEL", "llama3.1"), "prompt": prompt, "stream": False},
                )
                response.raise_for_status()
                text = response.json().get("response", "")[:1200]
        except Exception:
            return await super().generate_plan(engagement, imports)
        plan = await super().generate_plan(engagement, imports)
        plan.safety_notes.append(f"Ollama planning note: {text}")
        return plan


class OpenAIProvider(LocalRuleBasedProvider):
    name = ProviderName.openai


class ClaudeProvider(LocalRuleBasedProvider):
    name = ProviderName.claude


class DeepSeekProvider(LocalRuleBasedProvider):
    name = ProviderName.deepseek


def _planning_prompt(engagement: dict[str, Any], imports: list[dict[str, Any]]) -> str:
    endpoint_count = sum(len(item.get("endpoints", [])) for item in imports)
    return (
        "Create a safe, authorized-only bug bounty/API security testing plan. "
        "No exploit execution, no credential attacks, no brute force, no stealth, no persistence, no data extraction. "
        f"Engagement: {engagement.get('name')} mode={engagement.get('mode')} endpoints={endpoint_count}. "
        "Return concise analyst guidance."
    )


PROVIDERS: dict[ProviderName, AIProvider] = {
    ProviderName.local_rule_based: LocalRuleBasedProvider(),
    ProviderName.ollama: OllamaProvider(),
    ProviderName.openai: OpenAIProvider(),
    ProviderName.claude: ClaudeProvider(),
    ProviderName.deepseek: DeepSeekProvider(),
}


def get_provider(name: str | ProviderName) -> AIProvider:
    try:
        provider_name = ProviderName(name)
    except ValueError:
        provider_name = ProviderName.local_rule_based
    return PROVIDERS.get(provider_name, PROVIDERS[ProviderName.local_rule_based])
