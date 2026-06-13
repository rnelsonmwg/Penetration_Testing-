"""Provider registry + core model behavior."""

from thothansi.core.models import Asset, AssetType, Finding, Run, ReconResult, Severity
from thothansi.providers import ProviderConfig, available_providers, get_provider


def test_all_expected_providers_registered():
    assert set(available_providers()) == {
        "ollama", "claude", "openai", "groq", "deepseek", "grok"
    }


def test_get_provider_applies_default_model():
    assert get_provider("groq", ProviderConfig()).config.model == "llama-3.3-70b-versatile"
    assert get_provider("claude", ProviderConfig()).config.model == "claude-sonnet-4-6"


def test_remote_provider_unavailable_without_key():
    assert get_provider("claude", ProviderConfig()).is_available() is False


def test_severity_rank_ordering():
    assert Severity.CRITICAL.rank > Severity.HIGH.rank > Severity.INFO.rank


def test_finding_autogenerates_stable_id():
    f1 = Finding(title="x", asset="a.com", source="dns")
    f2 = Finding(title="x", asset="a.com", source="dns")
    assert f1.id == f2.id and len(f1.id) == 12


def test_effective_severity_prefers_triage():
    f = Finding(title="x", severity=Severity.LOW)
    assert f.effective_severity == Severity.LOW
    f.triage_severity = Severity.HIGH
    assert f.effective_severity == Severity.HIGH


def test_run_dedupes_and_sorts_findings():
    run = Run(targets=["a.com"])
    r = ReconResult(module="dns", target="a.com")
    r.findings = [
        Finding(title="low", severity=Severity.LOW, source="dns"),
        Finding(title="crit", severity=Severity.CRITICAL, source="dns"),
        Finding(title="low", severity=Severity.LOW, source="dns"),  # dup id
    ]
    r.assets = [
        Asset(type=AssetType.IP, value="1.1.1.1", source="dns"),
        Asset(type=AssetType.IP, value="1.1.1.1", source="dns"),  # dup
    ]
    run.results.append(r)
    findings = run.all_findings()
    assert len(findings) == 2                      # de-duplicated
    assert findings[0].title == "crit"             # highest severity first
    assert len(run.all_assets()) == 1              # de-duplicated
    assert run.severity_counts()["critical"] == 1
