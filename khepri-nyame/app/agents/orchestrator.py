from __future__ import annotations

from app.agents.api_mapper_agent import ApiMapperAgent
from app.agents.authz_agent import AuthzTesterAgent
from app.agents.base import AgentContext, BaseAgent
from app.agents.recon_agent import ReconAgent
from app.agents.report_agent import ReportWriterAgent
from app.agents.risk_agent import RiskPrioritizationAgent
from app.agents.secret_agent import SecretReviewAgent
from app.models.schemas import Finding

AGENTS: dict[str, BaseAgent] = {
    "recon": ReconAgent(),
    "api_mapper": ApiMapperAgent(),
    "authz": AuthzTesterAgent(),
    "secret_review": SecretReviewAgent(),
    "risk": RiskPrioritizationAgent(),
    "report": ReportWriterAgent(),
}

DEFAULT_AGENT_ORDER = ["recon", "api_mapper", "authz", "secret_review", "risk", "report"]


def run_agents(context: AgentContext, selected_agents: list[str] | None = None) -> list[Finding]:
    selected = selected_agents or DEFAULT_AGENT_ORDER
    all_findings: list[Finding] = []
    context.setdefault("findings", [])
    for agent_name in selected:
        agent = AGENTS.get(agent_name)
        if not agent:
            continue
        findings = agent.run(context)
        all_findings.extend(findings)
        context["findings"].extend([f.model_dump() for f in findings])
    return all_findings
