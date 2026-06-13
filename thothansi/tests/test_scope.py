"""Scope is the safety core — these tests guard it."""

import pytest

from thothansi.core.scope import Scope, ScopeFileError, ScopeViolation


@pytest.fixture
def scope():
    s = Scope("test")
    s.add("example.com")
    s.add("*.staging.example.com")
    s.add("api.acme.io")
    s.add("10.0.0.0/24")
    s.add_out_of_scope("secret.example.com")
    return s


@pytest.mark.parametrize(
    "target,expected",
    [
        ("example.com", True),
        ("www.example.com", True),
        ("https://example.com/path?q=1", True),
        ("example.com:8443", True),
        ("staging.example.com", True),        # in scope via example.com apex
        ("app.staging.example.com", True),
        ("a.b.staging.example.com", True),
        ("secret.example.com", False),         # explicit deny overrides allow
        ("api.acme.io", True),
        ("acme.io", False),                    # apex not listed
        ("notexample.com", False),             # suffix-spoof must fail
        ("evil.com", False),
        ("10.0.0.55", True),
        ("10.0.1.5", False),
    ],
)
def test_in_scope(scope, target, expected):
    assert scope.is_in_scope(target) is expected


def test_empty_scope_denies_everything():
    assert Scope("empty").is_in_scope("example.com") is False


def test_wildcard_matches_subdomains_only():
    s = Scope("w")
    s.add("*.staging.example.com")
    assert s.is_in_scope("staging.example.com") is False   # apex excluded
    assert s.is_in_scope("app.staging.example.com") is True
    assert s.is_in_scope("a.b.staging.example.com") is True


def test_assert_raises_for_out_of_scope(scope):
    with pytest.raises(ScopeViolation):
        scope.assert_in_scope("evil.com")


def test_assert_returns_normalized_host(scope):
    assert scope.assert_in_scope("HTTPS://WWW.Example.com/x") == "www.example.com"


def test_filter_splits_allowed_and_refused(scope):
    allowed, refused = scope.filter_in_scope(["example.com", "evil.com", "10.0.0.9"])
    assert allowed == ["example.com", "10.0.0.9"]
    assert refused == ["evil.com"]


def test_dynamic_add_is_audited(scope):
    before = len(scope.audit_log)
    scope.add("new.example.com", note="authorized via ticket-123")
    assert len(scope.audit_log) == before + 1
    assert "new.example.com" in scope.audit_log[-1]


def test_roundtrip_file(tmp_path, scope):
    p = tmp_path / "scope.yaml"
    scope.save(p)
    loaded = Scope.from_file(p)
    assert loaded.is_in_scope("app.staging.example.com")
    assert not loaded.is_in_scope("secret.example.com")


def test_missing_file_raises_clean_error(tmp_path):
    with pytest.raises(ScopeFileError) as ei:
        Scope.from_file(tmp_path / "nope.yaml")
    assert "init" in ei.value.hint.lower()


def test_malformed_yaml_raises_clean_error_with_location(tmp_path):
    p = tmp_path / "scope.yaml"
    p.write_text(
        'in_scope:\n'
        '   - value: "example.com"\n'
        '    note: "misaligned"\n'  # under-indented -> ParserError
    )
    with pytest.raises(ScopeFileError) as ei:
        Scope.from_file(p)
    assert "malformed" in ei.value.message.lower()
    assert "indentation" in ei.value.hint.lower()


def test_wrong_root_type_raises_clean_error(tmp_path):
    p = tmp_path / "scope.yaml"
    p.write_text("- just\n- a\n- list\n")
    with pytest.raises(ScopeFileError):
        Scope.from_file(p)


def test_in_scope_must_be_list(tmp_path):
    p = tmp_path / "scope.yaml"
    p.write_text('in_scope: "example.com"\n')
    with pytest.raises(ScopeFileError) as ei:
        Scope.from_file(p)
    assert "list" in ei.value.message.lower()


def test_entry_without_value_raises(tmp_path):
    p = tmp_path / "scope.yaml"
    p.write_text("in_scope:\n  - note: \"no value here\"\n")
    with pytest.raises(ScopeFileError):
        Scope.from_file(p)


def test_valid_file_with_notes_loads(tmp_path):
    p = tmp_path / "scope.yaml"
    p.write_text(
        'engagement: "eng"\n'
        'in_scope:\n'
        '  - value: "example.com"\n'
        '    note: "primary"\n'
        '  - "plain.example.org"\n'
        'out_of_scope:\n'
        '  - value: "secret.example.com"\n'
    )
    s = Scope.from_file(p)
    assert s.is_in_scope("www.example.com")
    assert s.is_in_scope("plain.example.org")
    assert not s.is_in_scope("secret.example.com")
