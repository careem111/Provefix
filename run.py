"""Run ProveFix on one scenario: python run.py scenarios/network-policy"""
import json
import sys
from pathlib import Path

from agent.loop import run_finding
from agent.provider import get_provider
from sandbox import cluster


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    folder = Path(argv[1])
    finding = json.loads((folder / "finding.json").read_text())
    provider = get_provider()
    print(f"provider: {type(provider).__name__}  cluster: {cluster.CONTEXT}")
    cluster.preflight()

    result = run_finding(finding, provider)
    print()
    if result.status == "fixed":
        print(f"FIXED in {result.attempts} attempt(s), proof level {result.proof_level}: attack blocked, app healthy.")
        return 0
    if result.status == "not_exploitable":
        print("NOT EXPLOITABLE: the attack did not work, no fix attempted.")
        return 0
    print(f"ESCALATED: no fix passed all proofs in {result.attempts} attempts.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
