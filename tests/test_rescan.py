"""Rescan failures must name the control and the resources that failed it.

The retry loop feeds this message back to the model, so "C-0260=failed" alone
is unactionable — the model can't learn which workload is still uncovered.
These tests use fabricated reports, so no kubescape binary is needed.
"""
from proof.rescan import _failed_resources, _summarize

REPORT = {
    "summaryDetails": {"controls": {
        "C-0260": {"status": "failed", "name": "Missing network policy"},
        "C-0057": {"status": "passed", "name": "Privileged container"},
    }},
    "results": [
        {"resourceID": "path=1/api=apps/v1//Deployment/api",
         "controls": [{"controlID": "C-0260", "status": {"status": "failed"}}]},
        {"resourceID": "path=2/api=apps/v1//Deployment/db",
         "controls": [{"controlID": "C-0260", "status": {"status": "passed"}}]},
    ],
}


def test_pass_stays_compact():
    assert _summarize(REPORT, ["C-0057"]) == (True, "kubescape: C-0057=passed")


def test_failure_names_control_and_failed_resources():
    passed, detail = _summarize(REPORT, ["C-0260"])
    assert not passed
    assert "C-0260=failed" in detail
    assert "Missing network policy" in detail
    assert "Deployment/api" in detail
    assert "Deployment/db" not in detail


def test_failure_without_results_section_does_not_crash():
    report = {"summaryDetails": {"controls": {
        "C-0260": {"status": "failed", "name": "Missing network policy"}}}}
    passed, detail = _summarize(report, ["C-0260"])
    assert not passed and "C-0260=failed" in detail


def test_missing_control_is_reported_honestly():
    passed, detail = _summarize(REPORT, ["C-9999"])
    assert not passed and "C-9999=missing" in detail


def test_failed_resources_accepts_string_or_object_status():
    report = {"results": [
        {"resourceID": "path=1/api=apps/v1//Deployment/a",
         "controls": [{"controlID": "C-0260", "status": {"status": "failed"}}]},
        {"resourceID": "path=2/api=/v1//ConfigMap/b",
         "controls": [{"controlID": "C-0260", "status": "failed"}]},
    ]}
    assert _failed_resources(report, ["C-0260"]) == {"C-0260": ["Deployment/a", "ConfigMap/b"]}
