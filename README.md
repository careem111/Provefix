# ProveFix

**An AI agent that fixes Kubernetes security problems — and proves each fix actually works.**

> Built for the Meta Global AI Developer Hackathon · Indie track · Theme: Build for Your World

---

## What ProveFix does

Security scanners are good at **finding** problems in Kubernetes, but they don't fix them. Newer AI tools can **write** a fix, but they can't tell you whether the fix really worked — they just scan again and hope.

ProveFix is different. It writes a fix **and then proves it** by actually re-running the attack:

- If the attack is now blocked **and** the app still works, the fix is accepted.
- If not, it tries again.

Think of a locksmith who doesn't just change your lock — they try to break in again afterwards to show you the new lock actually holds.

---

## The problems it solves

ProveFix works on real Kubernetes security issues. Two examples it handles today:

**1\. An exposed database.** A database with no rule about who can connect to it — **any** app in the cluster can reach it and read its data. In the real world this is an open production database: if one app gets hacked, the attacker walks straight in.

**2\. An over-powered container.** A container running with "privileged" access, which lets it break out of its box and reach the underlying machine. If that container is compromised, the attacker can take over the host — and often the whole cluster.

In both cases a scanner will flag the issue, but flagging isn't fixing — and a careless fix might stop the attacker while accidentally breaking the real app. ProveFix handles both sides.

---

## How it works

For any one security problem, the agent runs these steps:

1. **Confirm it's real.** It runs the actual attack. If the attack works, the problem is genuine.
2. **Ask the AI for a fix.** It sends the problem to the AI model, which writes the fix.
3. **Check the AI didn't cheat.** Before touching anything, it makes sure the fix didn't just *delete* the thing it was meant to protect, to make the problem "disappear."
4. **Prove the fix.** It applies the fix, then checks three things independently:
    - the attack is now **blocked**,
    - the real app **still works**, and
    - an independent scanner **agrees** the problem is gone.
5. **Retry if needed.** If any check fails, the error goes back to the AI and it tries again — up to 3 times.

Only when all three checks pass is the fix accepted. A fix is **proven, not assumed**.

---

## The AI behind it

ProveFix uses **Meta's Muse Spark model** (`muse-spark-1.1`), through the **Meta Model API**, as its brain. The AI's one job is to **write the fix**. Everything that decides whether to *trust* that fix — confirming the attack, catching cheating, applying the change, and proving it worked — is ordinary, predictable code. So the AI is powerful but never blindly trusted: its work is always checked.

---

## What's inside

- **Provider** — talks to the AI: sends the problem, cleans up the reply, and makes sure it's valid.
- **Loop** — runs the whole flow: confirm → fix → prove → retry.
- **Proof checks** — the independent verifiers: the attack replay, the app health check, a "did it cheat?" check, and a scanner re-check.
- **Sandbox** — does all the work safely inside a throwaway space on a local test cluster. It won't even start unless the safety setup is in place.
- **Scenario** — a self-contained practice problem (the broken setup, the attack, the health check, and a description of the issue).

**Tech stack:** Python 3.12 · Meta Muse Spark (via Meta Model API) · kind + Calico (local Kubernetes) · Kubescape (security scanner)

---

## Scenarios covered

| Problem | The fix the AI writes | Checked against |
| --- | --- | --- |
| Exposed database — any pod can reach it | A network rule allowing only the real app to connect | Kubescape C-0260 · ISO 27001 A.8.22 · SOC 2 CC6.6 |
| Privileged container — can escape to the host | Rewrites the container to drop its privileges and host access | Kubescape C-0057 · ISO 27001 A.8.2 · SOC 2 CC6.1 |

Each fix must block the real attack **and** keep the app healthy **and** satisfy the scanner before it's accepted.

---

## What we tested in the demo

We ran the full agent against the **real Muse Spark model** on a local test cluster.

**Exposed database:**

bash

```bash
PROVIDER=muse python run.py scenarios/network-policy
```

The AI **blocked the attack on its very first try, every time.** The only reason it sometimes needed a second or third try was to also match the scanner's exact requirements — and the retry loop handled that automatically, reaching a fully clean, proven result in 2–3 attempts.

This is the whole point of ProveFix: a fix can genuinely stop an attack **but still not satisfy a scanner** — and only a tool that checks *both* the real attack and the scanner can tell the difference.

**Privileged container:**

bash

```bash
PROVIDER=muse python run.py scenarios/privileged-container
```

The agent confirms the container can read the host's files, the AI strips the container's privileges, and the same proof loop confirms the escape now fails, the app still runs, and the scanner (C-0057) passes.

Each scenario can also be run offline with a pre-written fix (no AI calls, free) by setting `PROVIDER=mock`. The project includes 27 passing unit tests.

---

## Try it yourself

bash

```bash
# 1. Install the tools
brew install kind kubectl
curl -s https://raw.githubusercontent.com/kubescape/kubescape/master/install.sh | /bin/bash

# 2. Create a local cluster that can enforce network rules
cat > kind-calico.yaml <<'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  disableDefaultCNI: true
  podSubnet: "192.168.0.0/16"
EOF
kind create cluster --name provefix --config kind-calico.yaml
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.28.0/manifests/calico.yaml
# wait until all kube-system pods show Running

# 3. Add your API key
echo "MODEL_API_KEY=your_key_here" > .env

# 4. Set up Python
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 5. Run a scenario
set -a; source .env; set +a
PROVIDER=muse python run.py scenarios/network-policy
PROVIDER=muse python run.py scenarios/privileged-container
```

**No API key?** Run either scenario offline with a pre-written fix (free):

bash

```bash
PROVIDER=mock python run.py scenarios/network-policy
```

---

## What's built, and what's next

**Built and proven today:** the full confirm → fix → prove → retry agent, running end to end against the real Muse Spark model, on two scenarios — an exposed database and a privileged container.

**Roadmap:**

- More scenarios (over-permissioned access, and beyond) — the scenario format is already generic
- Pulling problems automatically from production scanners (Kubescape, Wiz, Snyk)
- A human-approval step and automatic GitHub pull requests with the proof attached
- Support for Terraform / AWS, not just Kubernetes
- A GitHub Action so ProveFix runs on every pull request

---

## Limitations

ProveFix proves that a **known attack is blocked** and the app still works. It doesn't prove a fix is perfect in every possible way — it's only as thorough as the attack and health checks written for each scenario.
