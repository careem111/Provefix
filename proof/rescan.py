import json
import tempfile
from pathlib import Path

from sandbox.cluster import describe, run


def _status(value):
    """Kubescape reports status as a string or as {"status": ...}; accept both."""
    return value.get("status") if isinstance(value, dict) else value


def _failed_resources(report, controls):
    """Map each failed control to the Kind/name labels that failed it.

    resourceIDs look like "path=<hash>/api=apps/v1//Deployment/api";
    the last two segments are always Kind and name.
    """
    wanted, failed = set(controls), {}
    for entry in report.get("results") or []:
        parts = (entry.get("resourceID") or "").split("/")
        if len(parts) < 2:
            continue
        label = f"{parts[-2]}/{parts[-1]}"
        for ctrl in entry.get("controls") or []:
            if ctrl.get("controlID") in wanted and _status(ctrl.get("status")) == "failed":
                failed.setdefault(ctrl["controlID"], []).append(label)
    return failed


def _summarize(report, controls):
    """Turn a Kubescape report into (passed, detail).

    Failures name the control and the resources that failed it, because the
    retry loop feeds this message back to the model: "C-0260=failed" alone
    tells it nothing about what is still uncovered.
    """
    info = report.get("summaryDetails", {}).get("controls", {})
    statuses = {c: _status(info.get(c, {}).get("status", "missing")) for c in controls}
    if all(s == "passed" for s in statuses.values()):
        return True, "kubescape: " + ", ".join(f"{c}=passed" for c in controls)
    failed = _failed_resources(report, controls)
    bits = []
    for c in controls:
        bit = f"{c}={statuses[c]}"
        if info.get(c, {}).get("name"):
            bit += f" ({info[c]['name']})"
        if c in failed:
            bit += f" on {', '.join(sorted(set(failed[c])))}"
        bits.append(bit)
    return False, "kubescape: " + "; ".join(bits)


def clean(manifest, controls, timeout=120):
    """Proof: Kubescape reports every given control as passed on the manifest. Returns (passed, detail)."""
    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp) / "manifest.yaml", Path(tmp) / "report.json"
        src.write_text(manifest)
        proc = run(["kubescape", "scan", "control", ",".join(controls), str(src),
                    "--format", "json", "--output", str(out)], timeout=timeout)
        if proc.returncode != 0 or not out.exists():
            return False, "kubescape failed\n" + describe(proc)
        report = json.loads(out.read_text())
    return _summarize(report, controls)
