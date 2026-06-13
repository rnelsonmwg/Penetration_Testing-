from pathlib import Path

from app.agents.base import AgentContext
from app.agents.orchestrator import run_agents
from app.parsers.input_parsers import parse_import


def test_agents_generate_safe_findings():
    content = Path("examples/sample_openapi.yaml").read_text()
    endpoints, metadata = parse_import("openapi", content)
    context = AgentContext(
        engagement={"id": "test", "name": "Unit Test", "mode": "guided_wizard", "provider": "local-rule-based", "scope": ["https://api.example.test"]},
        imports=[{"name": "sample", "source_type": "openapi", "raw_preview": content, "endpoints": endpoints, "metadata": metadata}],
        findings=[],
    )
    findings = run_agents(context)
    assert findings
    assert any(f.category == "authorization" for f in findings)
    assert all("brute" not in f.description.lower() for f in findings)
