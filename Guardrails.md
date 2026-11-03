# ProveFix — Guardrails

ProveFix is an AI agent that modifies Kubernetes configuration. An agent that edits infrastructure needs hard limits: it must only act inside a safe sandbox, must never be tricked into a destructive "fix," and must not run away with cost or loop forever. These are the guardrails that enforce that.

Guardrails marked **\[enforced\]** are active in the current code. Those marked **\[design\]** are part of the production plan and are on the roadmap.

---

## 1\. Blast radius — where the agent is allowed to act

- **\[enforced\] Single cluster only.** The sandbox targets one cluster, `kind-provefix`. It will not run against any other kube-context, so it cannot reach a real or shared cluster.
- **\[enforced\] Refuses an unsafe cluster.** It will not start unless Calico is present and enforcing network policy. This guarantees the environment is the known-good local sandbox (and that policy tests are real, not silently ignored).
- **\[enforced\] Fresh, isolated namespace per run.** Each run creates its own namespace and deletes it afterward, so runs can't interfere with each other or leave residue.
- **\[enforced\] No escaping the namespace.** Manifests that declare their own namespace or create cluster-wide / cluster-scoped resources are rejected. A fix can only affect the throwaway namespace it runs in.
- **\[enforced\] Never touches production.** All work happens on the local kind cluster. Nothing is applied to any remote or production environment.

## 2\. Checking the AI's work before trusting it

- **\[enforced\] Confirm first.** The attack must actually succeed against the vulnerable setup before any fix is attempted. A finding that can't be reproduced is not "fixed" blindly.
- **\[enforced\] Anti-cheat runs before anything is applied.** The proposed fix is compared against the original: if it deletes a workload or service, or changes a selector, it is rejected *before* it reaches the cluster. A fix that "passes" by deleting the database never runs.
- **\[enforced\] A fix must pass three independent checks.** It is accepted only when all three agree: the attack is now blocked (exploit replay fails), the application is still healthy (smoke test passes), and an independent scanner confirms the control passes (Kubescape). No single check can green-light a fix — in particular, a clean scan alone is never enough.

## 3\. Containing the AI model

- **\[enforced\] Replies are validated.** The model's output has any formatting stripped and must parse as well-formed YAML before it can be applied. Malformed output is rejected, not applied.
- **\[enforced\] Bounded retries.** A fix is retried at most 3 times, then the finding is escalated instead of looping forever. This bounds both time and token spend.
- **\[enforced\] Bounded context on retries.** A retry resends only the original manifest and the last error — not the whole conversation — so context (and cost) stays flat across attempts.
- **\[enforced\] Bounded cost per call.** Reasoning effort is kept low and output tokens are capped, so no single call can run up a large bill.
- **\[enforced\] Offline mode.** A mock provider can run the entire pipeline with no API calls, so development and testing cost nothing and don't depend on the model.

## 4\. Credentials and secrets

- **\[enforced\] Key is never committed.** The API key lives in a `.env` file that is gitignored. The virtual environment and caches are gitignored too.
- **\[enforced\] No secrets in prompts or logs.** Only the finding and the manifest are sent to the model; credentials are never included.

## 5\. Fail-safe behavior

- **\[enforced\] Timeouts everywhere.** Every cluster and script command runs under a timeout, so a hang can't stall the pipeline.
- **\[enforced\] Loud failure, never silent success.** On any failed step, the agent prints the command, exit code, stdout and stderr. A step that cannot be verified is treated as a failure, not a pass.

## 6\. Human-in-the-loop (production design)

- **\[design\] Human approval before anything leaves the tool.** In production, a reviewer approves each fix before it is accepted, with the full before/after proof attached.
- **\[design\] Proposes, never auto-applies to production.** ProveFix opens a pull request against the application's repository; the existing review-and-deploy pipeline ships the change. The agent never applies a fix directly to a live cluster.
