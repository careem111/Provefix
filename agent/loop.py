"""The core loop: confirm -> fix -> prove -> retry (CLAUDE.md)."""
from dataclasses import dataclass, field
from pathlib import Path

from agent.provider import FixProvider, ROOT, scenario_dir
from proof import diff, exploit, rescan, smoke
from sandbox import cluster

MAX_ATTEMPTS = 3


@dataclass
class Result:
    finding_id: str
    status: str  # "fixed" | "not_exploitable" | "escalated"
    attempts: int = 0
    fix: str | None = None
    proof_level: int | None = None
    evidence: list = field(default_factory=list)


def log(msg):
    print(msg, flush=True)


def prove(finding, original, fix, folder):
    """Run every proof against a candidate fix. Returns (passed, steps) where steps is [(name, passed, detail)]."""
    steps = []

    def step(name, result):
        passed, detail = result
        steps.append((name, passed, detail))
        summary = next((line for line in detail.splitlines() if not line.startswith("$ ")), "")
        log(f"    {'PASS' if passed else 'FAIL'}  {name}: {summary}")
        if not passed:
            log("      " + detail.replace("\n", "\n      "))
        return passed

    # Cheap static checks first, so a cheating fix never reaches the cluster.
    if not step("anti-cheat diff", diff.check(original, fix)):
        return False, steps
    with cluster.sandbox("prove") as ns:
        if not step("apply fix", cluster.apply(ns, fix)):
            return False, steps
        if not step("exploit blocked", exploit.blocked(ns, folder)):
            return False, steps
        if not step("smoke test", smoke.healthy(ns, folder)):
            return False, steps
    controls = finding.get("kubescape_controls") or []
    if controls and not step("kubescape rescan", rescan.clean(fix, controls)):
        return False, steps
    return True, steps


def proof_level(finding, folder):
    has_exploit = (folder / "exploit.sh").is_file()
    has_smoke = (folder / "smoke.sh").is_file()
    if has_exploit and has_smoke:
        return 3
    return 2 if has_smoke else 1


def run_finding(finding, provider: FixProvider) -> Result:
    folder = scenario_dir(finding)
    manifest_path = Path(finding["manifest_path"])
    original = (manifest_path if manifest_path.is_absolute() else ROOT / manifest_path).read_text()
    result = Result(finding["id"], "escalated")

    log(f"[{finding['id']}] confirm: replaying the attack against the vulnerable manifest")
    with cluster.sandbox("confirm") as ns:
        ok, detail = cluster.apply(ns, original)
        if not ok:
            raise cluster.SandboxError("vulnerable manifest failed to apply\n" + detail)
        worked, exploit_output = exploit.attack(ns, folder)
    result.evidence.append(("confirm", worked, exploit_output))
    if not worked:
        log("    attack did not work: not exploitable, skipping fix\n" + exploit_output)
        result.status = "not_exploitable"
        return result
    log("    attack works: finding confirmed")

    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result.attempts = attempt
        log(f"[{finding['id']}] fix: attempt {attempt}/{MAX_ATTEMPTS}")
        try:
            fix = provider.generate_fix(finding, original,
                                        exploit_output=None if last_error else exploit_output,
                                        last_error=last_error)
        except ValueError as e:
            log(f"    FAIL  provider returned an unusable fix: {e}")
            result.evidence.append((f"attempt {attempt}", False, [("generate fix", False, str(e))]))
            last_error = str(e)
            continue
        log(f"[{finding['id']}] prove: attempt {attempt}")
        passed, steps = prove(finding, original, fix, folder)
        result.evidence.append((f"attempt {attempt}", passed, steps))
        if passed:
            result.status, result.fix = "fixed", fix
            result.proof_level = proof_level(finding, folder)
            return result
        name, _, detail = next(s for s in steps if not s[1])
        last_error = f"{name} failed: {detail}"

    log(f"[{finding['id']}] no fix passed after {MAX_ATTEMPTS} attempts: escalating to a human")
    return result
