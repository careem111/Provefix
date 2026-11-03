"""Every scenario folder must follow the DEVELOPMENT.md contract.

These checks need no cluster: file layout, finding shape, YAML validity,
sandbox safety, and the mock fix sequence (bad attempt rejected, real fix kept).
"""
import json
from pathlib import Path

import pytest
import yaml

from agent.provider import MockFixProvider
from proof.diff import check
from sandbox.cluster import validate_manifest

SCENARIOS = Path(__file__).resolve().parent.parent / "scenarios"
FOLDERS = sorted(p for p in SCENARIOS.iterdir() if p.is_dir() and p.name != "_lib")

REQUIRED_FILES = ("vulnerable.yaml", "exploit.sh", "smoke.sh", "finding.json", "fix.yaml")
REQUIRED_FINDING_KEYS = ("id", "rule", "resource", "namespace", "manifest_path")


def test_at_least_one_scenario_exists():
    assert FOLDERS, "no scenario folders found"


@pytest.mark.parametrize("folder", FOLDERS, ids=[p.name for p in FOLDERS])
def test_required_files_present(folder):
    for name in REQUIRED_FILES:
        assert (folder / name).is_file(), f"missing {name}"


@pytest.mark.parametrize("folder", FOLDERS, ids=[p.name for p in FOLDERS])
def test_finding_shape(folder):
    finding = json.loads((folder / "finding.json").read_text())
    for key in REQUIRED_FINDING_KEYS:
        assert finding.get(key), f"finding.json lacks {key!r}"
    target = SCENARIOS.parent / finding["manifest_path"]
    assert target.resolve() == (folder / "vulnerable.yaml").resolve()


@pytest.mark.parametrize("folder", FOLDERS, ids=[p.name for p in FOLDERS])
def test_manifests_parse_and_stay_in_sandbox(folder):
    for name in ("vulnerable.yaml", "fix.yaml", *sorted(p.name for p in folder.glob("fix_attempt*.yaml"))):
        text = (folder / name).read_text()
        docs = [d for d in yaml.safe_load_all(text) if d]
        assert docs and all("kind" in d for d in docs), name
        assert validate_manifest(text) == [], name


@pytest.mark.parametrize("folder", FOLDERS, ids=[p.name for p in FOLDERS])
def test_mock_fix_sequence(folder):
    """Bad mock attempts fail the anti-cheat diff; fix.yaml passes it."""
    vulnerable = (folder / "vulnerable.yaml").read_text()
    for attempt in sorted(folder.glob("fix_attempt*.yaml")):
        passed, _ = check(vulnerable, attempt.read_text())
        assert not passed, f"{attempt.name} should be rejected by the anti-cheat diff"
    assert check(vulnerable, (folder / "fix.yaml").read_text())[0]


@pytest.mark.parametrize("folder", FOLDERS, ids=[p.name for p in FOLDERS])
def test_scripts_source_the_shared_lib(folder):
    for name in ("exploit.sh", "smoke.sh"):
        text = (folder / name).read_text()
        assert text.startswith("#!/usr/bin/env bash"), name
        assert '../_lib/probe.sh' in text, name


def test_privileged_scenario_meaning():
    folder = SCENARIOS / "privileged-container"
    vulnerable = (folder / "vulnerable.yaml").read_text()
    fixed = (folder / "fix.yaml").read_text()
    assert "privileged: true" in vulnerable
    assert "hostPID: true" in vulnerable
    assert "privileged: false" in fixed
    assert "hostPID" not in fixed
    assert "allowPrivilegeEscalation: false" in fixed
    assert 'drop: ["ALL"]' in fixed
    assert "runAsNonRoot: true" in fixed
    finding = json.loads((folder / "finding.json").read_text())
    assert finding["kubescape_controls"] == ["C-0057"]
    passed, detail = check(vulnerable, (folder / "fix_attempt1.yaml").read_text())
    assert not passed and "Deployment/worker was deleted" in detail


def test_privileged_mock_provider_sequence():
    finding = json.loads((SCENARIOS / "privileged-container" / "finding.json").read_text())
    provider = MockFixProvider()
    first = provider.generate_fix(finding, "")
    assert "kind: Deployment" not in first  # bad attempt 1 deletes the app
    assert "privileged: false" in provider.generate_fix(finding, "")
