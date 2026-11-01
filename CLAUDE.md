# CLAUDE.md — ProveFix

Context for Claude Code. Read this before writing or changing anything.

## What ProveFix is

ProveFix is an AI agent that fixes Kubernetes security misconfigurations and **proves each fix works** before a human approves it. Unlike tools that only re-scan, ProveFix replays the actual attack before and after the fix, and checks the app still runs.

It is built for the Meta Global AI Developer Hackathon (Indie track). It must *use* Meta's Muse Spark model at runtime — that is the point of the project.

## The core loop (this is the heart of the project)

For each finding:
1. **Confirm** — run the scenario's `exploit.sh`. Exit 0 means the attack works and the finding is real. If it fails, mark the finding "not exploitable" and skip the fix.
2. **Fix** — send the manifest + finding + exploit output to Muse Spark. Get back a corrected manifest.
3. **Prove** — apply the fix in a fresh namespace, then:
   - re-run `exploit.sh` → must now **fail** (attack blocked)
   - run `smoke.sh` → must **pass** (app still healthy)
   - run the **diff check** → reject fixes that delete the Deployment or empty the pod selector (anti-cheat)
   - re-scan with Kubescape → should be clean
4. **Retry** — if any proof fails, send the finding, the **original** vulnerable manifest and the error from the last attempt back to Muse Spark and try again, up to **3 attempts**, then escalate to a human.
5. **Approve** — show the before/after evidence, ask `Approve? y/n`. On yes, open a GitHub PR with the patch, the evidence, and the control mapping.

Never apply a fix to a real cluster. ProveFix only works in the local kind cluster and only opens PRs — it never runs `kubectl apply` against anything but the sandbox namespace.

## Muse Spark API (how we call the model)

- Base URL: `https://api.meta.ai/v1`
- Model string: `muse-spark-1.1` (confirm the exact version at hackathon onboarding — may be 1.3)
- Auth: bearer token in env var `MODEL_API_KEY`
- It is **OpenAI-SDK compatible** — use the `openai` Python package pointed at the base URL. Confirm from the onboarding docs whether to call `chat.completions.create` or `responses.create`; default to `chat.completions.create` as it's the most compatible.

Canonical call pattern:

```python
from openai import OpenAI
import os

client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"])

resp = client.chat.completions.create(
    model="muse-spark-1.1",
    messages=[
        {"role": "system", "content": "You fix Kubernetes security issues. Return only valid YAML, no prose."},
        {"role": "user", "content": prompt},
    ],
    max_tokens=3000,          # a fix never needs more
    # reasoning_effort="low", # use the lowest that still produces correct fixes — biggest cost lever
)
fix_yaml = resp.choices[0].message.content
```

### Cost rules (the free credit is ~$150, keep it safe)
- Output tokens are ~3.4× the price of input tokens, and reasoning counts as output. Keep `reasoning_effort` as low as works.
- Cap `max_tokens` low.
- On retries, send the finding, the **original** vulnerable manifest and the last error — never the failed fix, never the whole conversation history. (Not the failed fix: if it deleted a resource, the model can't restore what it can't see.)
- Debug prompts on one scenario; run the full eval sparingly.

## Providers and env vars

The model sits behind `agent/provider.py`. `get_provider()` picks one from `PROVIDER`:

| Env var | Default | Meaning |
|---|---|---|
| `PROVIDER` | `mock` | `mock` (canned `fix*.yaml`, no API) or `muse` (Muse Spark). Any other value is an error. |
| `MODEL_API_KEY` | — | Muse Spark key. Only needed when `PROVIDER=muse` actually calls the API. |
| `MUSE_MODEL` | `muse-spark-1.1` | Model string (confirm at onboarding). |
| `MUSE_BASE_URL` | `https://api.meta.ai/v1` | Meta Model API base URL. |
| `MUSE_REASONING_EFFORT` | `low` | Passed as `reasoning_effort` on every Muse Spark call. |
| `KUBE_CONTEXT` | `kind-provefix` | Sandbox cluster; must be a `kind-*` context. |

## Tech stack

- Python 3.12
- `openai` SDK (for Muse Spark), `kubernetes` or shelling out to `kubectl`
- kind (local cluster) + **Calico** (so NetworkPolicies actually enforce)
- Kubescape (scanner). Trivy is optional/later.
- `gh` CLI for opening PRs
- Streamlit is optional; a terminal `y/n` prompt is the default approval gate

## Repo layout

```
provefix/
  adapters/    kubescape.py            # parse scanner JSON -> finding dicts
  agent/       provider.py             # FixProvider: MockFixProvider / MuseSparkProvider, get_provider()
               fixer.py                # builds the prompt, cleans/validates the reply (no API calls)
               loop.py                 # confirm -> fix -> prove -> retry
  sandbox/     cluster.py              # apply / run script / reset namespace
  proof/       exploit.py smoke.py diff.py rescan.py
  ui/          approve.py              # terminal y/n (Streamlit optional)
  eval/        run_all.py              # runs every scenario -> metrics table
  run.py                               # python run.py scenarios/<name>  — one scenario end to end
  tests/                               # pytest unit tests (no cluster needed)
  scenarios/
    _lib/probe.sh                      # shared helpers sourced by scenario scripts
    network-policy/        vulnerable.yaml exploit.sh smoke.sh finding.json fix.yaml fix_attempt1.yaml
    privileged-container/  vulnerable.yaml exploit.sh smoke.sh
    service-account/       vulnerable.yaml exploit.sh smoke.sh
  .env                                 # MODEL_API_KEY — never commit
  .gitignore
  README.md
```

## A finding (normalized shape)

```python
{
  "id": "no-netpol-data-ns",
  "rule": "missing-network-policy",
  "resource": "namespace/data",
  "namespace": "data",
  "manifest_path": "scenarios/network-policy/vulnerable.yaml",
  "kubescape_controls": ["C-0260"],   # controls the rescan proof must see as passed
}
```

## Scenario format

Each scenario is one folder with three core files, plus `finding.json` (until the Kubescape adapter exists) and mock-only fixes. The eval set and the test set are the same folders.

```
scenarios/network-policy/
  vulnerable.yaml   # the misconfigured app
  exploit.sh        # exit 0 = attack worked
  smoke.sh          # exit 0 = app healthy
  finding.json      # the finding for this scenario (normalized shape above)
  fix.yaml          # MOCK ONLY: the canned correct fix MockFixProvider returns
  fix_attemptN.yaml # MOCK ONLY: optional fix for attempt N (e.g. a bad attempt 1 to exercise retry/anti-cheat)
```

`fix*.yaml` files must never be put into a model prompt.

Scripts are plain bash and run against the current sandbox namespace (env `NS`, `KUBE_CONTEXT`). Keep them harmless (read a file, open a TCP connection) — no real exploits, no internet access.

## Proof levels (label every result)

- **Level 3** — exploit + smoke + rescan all ran (strongest)
- **Level 2** — smoke + rescan (finding had no exploit script)
- **Level 1** — rescan only

## Hidden variants

For validation, keep 1–2 extra exploit scripts the model never sees in its prompt. Use them only to check the fix. This proves ProveFix didn't just satisfy the one test it was shown.

## Metrics (eval/run_all.py prints these)

- **Fix success rate** — share of findings where all proofs pass
- **Scanner-passed-but-still-exploitable rate** — the headline; run the scanner-only baseline (scanner says "fixed", then check if the exploit still works)
- **Average attempts per fix**

## Conventions

- Fail loudly: if a step errors, print what ran, the exit code, and stdout/stderr.
- Every namespace is created fresh and deleted after each run — no leftover state.
- Add a timeout to every script run (e.g. 60s) so a hang can't stall the loop.
- Keep functions small and testable; the proof runners each take a namespace and return (passed: bool, detail: str).

## Build order (do not skip ahead)

1. **Phase 1 — one scenario end to end** (network-policy): sandbox runner, confirm, fix via Muse Spark, prove. One command → "attack blocked, app healthy."
2. **Phase 2 — widen + harden**: 3 scenario types × 2 variants, Kubescape adapter, retry loop, proof levels, anti-cheat diff, hidden variants.
3. **Phase 3 — output**: GitHub PR with evidence + control mapping, approval gate, eval table with the baseline.
4. **Phase 4 — ship**: README, architecture diagram, demo video. Freeze features Nov 3.

Build Phase 1 fully before anything else — it de-risks the API and the proof loop on day one.

## Do NOT

- Commit `.env` or the API key.
- Call Muse Spark with the whole history on retries.
- Apply fixes anywhere except the sandbox namespace.
- Trust a "blocked" NetworkPolicy result without Calico installed — verify enforcement first.
- Add features after the Nov 3 freeze.

