"""Triage: structured parsing, severity adjustment, and safe degradation."""

import json

from thothansi.core.models import Finding, ReconResult, Run, Severity
from thothansi.providers import AIProvider, ProviderConfig, ProviderError, ProviderResponse
from thothansi.triage.analyzer import TriageAnalyzer, _extract_json_array


class _Echo(AIProvider):
    """Returns a fixed triage verdict for every finding id in the prompt."""
    name = "echo"; label = "Echo"; local = True; default_model = "echo"

    def is_available(self):
        return True

    def complete(self, prompt, system=None):
        import re
        ids = re.findall(r'"id":\s*"([0-9a-f]+)"', prompt)
        arr = [
            {"id": i, "severity": "high", "rationale": "r", "recommendation": "verify", "confidence": 0.9}
            for i in ids
        ]
        return ProviderResponse(text=json.dumps(arr), model="echo", provider="echo")


class _Broken(AIProvider):
    name = "broken"; label = "Broken"; local = True; default_model = "x"

    def is_available(self):
        return True

    def complete(self, prompt, system=None):
        raise ProviderError("boom")


def _run_with_findings():
    run = Run(targets=["a.com"])
    r = ReconResult(module="dns", target="a.com")
    r.findings = [
        Finding(title="f1", severity=Severity.LOW, source="dns"),
        Finding(title="f2", severity=Severity.INFO, source="dns"),
    ]
    run.results.append(r)
    return run


def test_extract_json_array_tolerates_code_fences():
    text = "```json\n[{\"id\": \"abc\"}]\n```"
    assert _extract_json_array(text) == [{"id": "abc"}]


def test_extract_json_array_finds_embedded_block():
    text = "Here is the result: [{\"id\": \"x\"}] thanks!"
    assert _extract_json_array(text) == [{"id": "x"}]


def test_triage_adjusts_severity():
    run = _run_with_findings()
    TriageAnalyzer(_Echo(ProviderConfig())).triage_run(run)
    for f in run.all_findings():
        assert f.effective_severity == Severity.HIGH
        assert f.triage_confidence == 0.9
    assert run.severity_counts()["high"] == 2


def test_triage_degrades_gracefully_on_provider_error():
    run = _run_with_findings()
    TriageAnalyzer(_Broken(ProviderConfig())).triage_run(run)
    # heuristic severities are preserved; nothing crashes, nothing dropped
    titles = {f.title for f in run.all_findings()}
    assert titles == {"f1", "f2"}
    assert run.all_findings()[0].triage_severity is None
