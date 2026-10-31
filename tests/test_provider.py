import builtins
from types import SimpleNamespace

import pytest

from agent.provider import MockFixProvider, MuseSparkProvider, get_provider

GOOD = "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: x\n"


def finding_in(folder):
    return {"id": "f1", "manifest_path": str(folder / "vulnerable.yaml")}


def test_factory_defaults_to_mock(monkeypatch):
    monkeypatch.delenv("PROVIDER", raising=False)
    assert isinstance(get_provider(), MockFixProvider)


def test_factory_selects_muse(monkeypatch):
    monkeypatch.setenv("PROVIDER", "muse")
    assert isinstance(get_provider(), MuseSparkProvider)


def test_factory_rejects_unknown(monkeypatch):
    monkeypatch.setenv("PROVIDER", "muze")
    with pytest.raises(ValueError, match="mock, muse"):
        get_provider()


def test_mock_sequences_attempts_then_falls_back(tmp_path):
    (tmp_path / "fix_attempt1.yaml").write_text(GOOD.replace("x", "first"))
    (tmp_path / "fix.yaml").write_text(GOOD.replace("x", "final"))
    p = MockFixProvider()
    f = finding_in(tmp_path)
    assert "first" in p.generate_fix(f, "")
    assert "final" in p.generate_fix(f, "")
    assert "final" in p.generate_fix(f, "")


def test_mock_counts_attempts_per_finding(tmp_path):
    (tmp_path / "fix_attempt1.yaml").write_text(GOOD.replace("x", "first"))
    (tmp_path / "fix.yaml").write_text(GOOD)
    p = MockFixProvider()
    p.generate_fix(finding_in(tmp_path), "")
    other = {**finding_in(tmp_path), "id": "f2"}
    assert "first" in p.generate_fix(other, "")


def test_mock_missing_fix_names_folder(tmp_path):
    with pytest.raises(FileNotFoundError, match="fix_attempt1.yaml, fix.yaml"):
        MockFixProvider().generate_fix(finding_in(tmp_path), "")


def test_mock_reads_real_scenario():
    f = {"id": "real", "manifest_path": "scenarios/network-policy/vulnerable.yaml"}
    p = MockFixProvider()
    assert "deny-all" in p.generate_fix(f, "")
    assert "db-allow-api" in p.generate_fix(f, "")


def test_muse_works_without_key_or_openai(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    real_import = builtins.__import__
    monkeypatch.setattr(builtins, "__import__",
                        lambda name, *a, **k: (_ for _ in ()).throw(ImportError(name)) if name == "openai"
                        else real_import(name, *a, **k))
    p = MuseSparkProvider()  # constructing it must not need the key or the package
    with pytest.raises(RuntimeError, match="MODEL_API_KEY"):
        p.generate_fix({"id": "f"}, GOOD)


def test_muse_reads_env_and_cleans_reply(monkeypatch):
    monkeypatch.setenv("MUSE_MODEL", "muse-spark-1.3")
    calls = {}

    def create(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=f"```yaml\n{GOOD}```"))])

    p = MuseSparkProvider()
    p._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    assert p.generate_fix({"id": "f"}, GOOD, last_error="smoke failed") == GOOD
    assert calls["model"] == "muse-spark-1.3"
    assert calls["max_tokens"] == 3000
    assert "smoke failed" in calls["messages"][1]["content"]
