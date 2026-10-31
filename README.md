ProveFix

Proven security fixes for Kubernetes.

ProveFix is an AI agent that fixes Kubernetes security misconfigurations and proves each fix actually works — by replaying the real attack before and after the fix, and checking the app still runs — before a human approves it and it opens a pull request.

The problem

Security scanners flag far more issues than teams can fix. Existing AI fix tools check their own work only by re-scanning, which proves nothing about whether the attack is really stopped or whether the fix quietly broke the application.

How ProveFix is different
Confirms first. Replays the attack before fixing. If the attack doesn't work, the finding is deprioritized — no wasted fix.
Proves the fix. After fixing, the attack must now fail, the app smoke test must pass, and the change must not delete resources or break selectors.
Catches cheating. Rejects "fixes" that pass the scanner by deleting the app or blocking all traffic.
Hidden variants. Validates with exploit variants the model never saw, so a fix can't just satisfy one test.
Safe by design. Runs only in a local cluster; never touches production; only opens PRs for human approval.
How it works
Finding ─► Confirm (attack works?) ─► Fix (Muse Spark) ─► Prove (attack fails? app ok? no damage? clean scan?)
                                              ▲                        │
                                              └──── retry ≤ 3 ─────────┘
                                                                       │
                                                        Human approves ─► GitHub PR + evidence
Tech stack

Python 3.12 · Meta Muse Spark (via Meta Model API) · kind + Calico · Kubescape · GitHub CLI

Scenarios covered
Misconfiguration	Attack replayed	Control mapping
Missing NetworkPolicy	Frontend reaches the DB across namespaces	ISO A.8.22 / SOC 2 CC6.6
Privileged container	Pod escapes to the node namespace	ISO A.8.2 / SOC 2 CC6.1
Over-permissioned service account	Pod reads cluster secrets via the API	ISO A.8.2 / SOC 2 CC6.3
Results
<!-- Fill in from eval/run_all.py before submitting -->
Metric	ProveFix	Scanner-only baseline
Fix success rate	__%	n/a
Passed scan but still exploitable	__%	__%
Average attempts per fix	__	n/a
Quickstart
bash
# 1. Prerequisites
brew install kind kubectl helm trivy gh python@3.12
curl -s https://raw.githubusercontent.com/kubescape/kubescape/master/install.sh | /bin/bash

# 2. Cluster with an enforcing CNI
kind create cluster --name provefix
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.28.0/manifests/calico.yaml

# 3. Credentials
cp .env.example .env     # add your MODEL_API_KEY

# 4. Run against one scenario
python run.py scenarios/network-policy

# 5. Run the full eval
python -m provefix.eval.run_all
Demo
<!-- Add the 2–3 min video link before submitting -->

Attack works → human approves → attack fails → app still healthy → PR opens.

Limitations

ProveFix proves that known attack paths are closed and the app still works. It does not prove a fix is correct in every possible way. Coverage is as good as the exploit and smoke scripts written for each scenario.

Roadmap
Adapters for Snyk, Wiz and other scanners (the finding interface is already pluggable)
Terraform / AWS support, not just Kubernetes
A GitHub Action so ProveFix runs on every pull request