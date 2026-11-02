# ProveFix

**Proven security fixes for Kubernetes.**

ProveFix is an AI agent that fixes a Kubernetes security misconfiguration and then *proves the fix actually works* — it replays the real attack before and after the fix, and checks the application still runs — so a fix is accepted only when it's verified, not merely assumed.

> Built for the Meta Global AI Developer Hackathon · Indie track · Theme: Build for Your World

---

## How the agent is built

ProveFix is written in **Python 3.12** and uses **Meta's Muse Spark model** (`muse-spark-1.1`), accessed through the **Meta Model API**, as its reasoning engine. When a fix is needed, the agent sends the security finding and the current Kubernetes manifest to Muse Spark, which writes the corrected manifest. Everything around that call — confirming the problem, checking the fix for cheating, applying it, and proving it — is deterministic code, so the AI's suggestion is always independently verified before it's trusted.

The model integration sits behind a small provider interface, so the same pipeline can run against the live Muse Spark API or against a local stand-in for offline testing. The demo runs against the real Muse Spark API.

---

## Components of the agent

- **Provider** — talks to Muse Spark via the Meta Model API: builds the prompt, strips formatting, and validates that the reply is well-formed YAML. On a retry it resends the original manifest plus the last error, so the model always knows what to restore.
- **Loop** — orchestrates the flow: confirm → fix → prove → retry (up to 3 attempts).
- **Proof checks** — the independent verifiers: an anti-cheat diff, the attack replay (exploit), the application health check (smoke test), and a **Kubescape** rescan of the relevant control.
- **Sandbox** — runs everything in an isolated namespace on a local **kind** cluster. It refuses to start unless **Calico** is enforcing network policy, rejects manifests that touch cluster-wide resources, and puts a timeout on every command.
- **Scenario** — a self-contained test case (the vulnerable setup, the attack, the health check, and the finding description).

**Tech stack:** Python 3.12 · Meta Muse Spark (via Meta Model API) · kind + Calico · Kubescape

---

## The problem

A database running in Kubernetes with **no network restriction** — any pod in the cluster can connect to it and read its data. In the real world this is an exposed production database: if a single app is compromised, the attacker can reach the database directly. Security scanners flag this kind of issue, but they stop at detection. Even AI fix tools typically check their own work only by re-scanning, which proves nothing about whether the attack is really stopped or whether the fix quietly broke the application.

Mapped to Kubescape control **C-0260** (missing NetworkPolicy) · ISO 27001 A.8.22 · SOC 2 CC6.6.

---

## The fix

The agent asks Muse Spark to write a **NetworkPolicy** — a rule that allows only the legitimate application to reach the database and blocks everything else. Crucially, the fix must satisfy three independent conditions before it's accepted:

1. the attacker pod can **no longer** reach the database,
2. the legitimate app **can still** reach it, and
3. an independent scanner (Kubescape) agrees the control now passes.

A fix that blocks the attack but breaks the app, or that "passes" by deleting the database, is rejected.

---

## How we tested it in our demo

We ran the full pipeline against the **real Muse Spark API** on a local kind cluster with Calico enforcing:

```bash
PROVIDER=muse python run.py scenarios/network-policy
```

The run proceeds as:

1. **Confirm** — the agent launches an attacker pod that reads the database's secret. It succeeds, confirming the risk is real.
2. **Fix** — Muse Spark writes a NetworkPolicy.
3. **Anti-cheat** — the agent checks the fix keeps every workload and service intact (so the model can't "fix" it by deleting the database). This runs *before* anything is applied.
4. **Prove** — the fix is applied to a fresh namespace, then: the attack is replayed and now **fails**, the smoke test confirms the app is still **healthy**, and **Kubescape** confirms control **C-0260 now passes**.
5. **Retry** — if any check fails, the error is sent back to Muse Spark and it tries again.

**What we observed:** the model **blocked the attack on the very first attempt every time**. The extra attempts were only needed to also satisfy Kubescape's exact policy requirements, which the retry loop resolved automatically — reaching a fully clean state (**proof level 3**) in **2–3 attempts**. This is exactly the gap ProveFix is built to catch: a fix can genuinely stop an attack yet still not satisfy a scanner, and only a tool that verifies *both* the attack and the scan can tell the difference.

A free, offline run using a pre-written fix (no API calls) is also available for testing:
```bash
PROVIDER=mock python run.py scenarios/network-policy
```

The project also includes 27 passing unit tests.

---

## Quickstart

```bash
# 1. Tools
brew install kind kubectl
curl -s https://raw.githubusercontent.com/kubescape/kubescape/master/install.sh | /bin/bash

# 2. Cluster with an enforcing CNI (kind's default does NOT enforce NetworkPolicy)
cat > kind-calico.yaml <<'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  disableDefaultCNI: true
  podSubnet: "192.168.0.0/16"
EOF
kind create cluster --name provefix --config kind-calico.yaml
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.28.0/manifests/calico.yaml
# wait until all kube-system pods are Running

# 3. Credentials
echo "MODEL_API_KEY=your_key_here" > .env

# 4. Python environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 5. Run the scenario
set -a; source .env; set +a
PROVIDER=muse python run.py scenarios/network-policy
```

---

## Limitations

ProveFix proves that a **known attack path is closed** and the application still works. It does not prove a fix is correct in every possible way; coverage is as good as the attack and health-check scripts written for each scenario. The current demo covers one scenario (missing NetworkPolicy) end to end.

---

## Roadmap

- More scenarios (privileged container, over-permissioned service account) — the scenario format is already generic
- Automatic finding ingestion from production scanners (Kubescape, Wiz, Snyk) — the finding interface is already pluggable
- Human-approval gate and automatic GitHub pull requests with the proof attached
- Terraform / AWS support, not just Kubernetes
- A GitHub Action so ProveFix runs on every pull request

---

## License

MIT
