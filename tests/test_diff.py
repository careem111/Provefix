from pathlib import Path

from proof.diff import check
from sandbox.cluster import validate_manifest

SCENARIO = Path(__file__).resolve().parent.parent / "scenarios" / "network-policy"
VULN = (SCENARIO / "vulnerable.yaml").read_text()


def test_real_fix_passes():
    assert check(VULN, (SCENARIO / "fix.yaml").read_text())[0]


def test_cheat_attempt_is_rejected():
    passed, detail = check(VULN, (SCENARIO / "fix_attempt1.yaml").read_text())
    assert not passed and "Deployment/db was deleted" in detail


def test_emptied_selector_is_rejected():
    fixed = VULN.replace("  selector:\n    app: db\n", "  selector: {}\n")
    passed, detail = check(VULN, fixed)
    assert not passed and "Service/db selector was emptied" in detail


def test_changed_selector_is_rejected():
    passed, detail = check(VULN, VULN.replace("app: api", "app: nobody"))
    assert not passed and "selector changed" in detail


def test_scenario_manifests_are_sandbox_safe():
    for name in ("vulnerable.yaml", "fix.yaml", "fix_attempt1.yaml"):
        assert validate_manifest((SCENARIO / name).read_text()) == [], name


def test_manifest_escaping_the_sandbox_is_refused():
    errors = validate_manifest(
        "kind: ClusterRoleBinding\nmetadata: {name: x}\n---\n"
        "kind: Deployment\nmetadata: {name: y, namespace: kube-system}\n")
    assert any("kind not allowed" in e for e in errors)
    assert any("sets metadata.namespace" in e for e in errors)
