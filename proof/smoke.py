from sandbox.cluster import describe, run_script


def healthy(ns, scenario_dir):
    """Proof: smoke.sh must pass. Returns (passed, detail)."""
    proc = run_script(scenario_dir / "smoke.sh", ns)
    return proc.returncode == 0, describe(proc)
