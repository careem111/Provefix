import json
import tempfile
from pathlib import Path

from sandbox.cluster import describe, run


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
    results = report.get("summaryDetails", {}).get("controls", {})
    statuses = {c: results.get(c, {}).get("status", "missing") for c in controls}
    passed = all(s == "passed" for s in statuses.values())
    return passed, "kubescape: " + ", ".join(f"{c}={s}" for c, s in statuses.items())
