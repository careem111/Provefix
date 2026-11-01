Read DEVELOPMENT.md first. The Muse Spark API key isn't available yet, so build everything behind a provider interface.

## Scope

Phase 1 only (the network-policy scenario), per the build order in DEVELOPMENT.md. Build and test it end to end with MockFixProvider. Don't start Phase 2.

## Provider interface — `agent/provider.py`

Create an abstract `FixProvider` class with:

```python
def generate_fix(self, finding: dict, manifest: str, exploit_output: str | None = None, last_error: str | None = None) -> str
```

It returns the corrected manifest as a YAML string. Every implementation must:
- Strip Markdown code fences (```` ```yaml ```` / ```` ``` ````) if present.
- Check the result parses as YAML (multi-document allowed) and raise a clear error if not.

`agent/fixer.py` builds the prompt and delegates the model call to the provider. Keep prompt building out of the providers.

### MockFixProvider
- Ignores the API entirely.
- Resolves the scenario folder as the directory containing `finding["manifest_path"]`.
- Supports scripted attempts so the retry loop can be tested. On attempt N (1-based, tracked per finding id), return `fix_attemptN.yaml` if it exists, otherwise fall back to `fix.yaml`.
- If neither file exists, raise an error naming the folder and the files it looked for.

### MuseSparkProvider
- Calls the Meta Model API as described in DEVELOPMENT.md (`openai` SDK, `chat.completions.create`, low `max_tokens`).
- Config comes from env vars with defaults: `MODEL_API_KEY` (required only when actually calling), `MUSE_MODEL` (default `muse-spark-1.1`), `MUSE_BASE_URL` (default `https://api.meta.ai/v1`).
- Create the client lazily, on the first `generate_fix` call. Importing the module or running with `PROVIDER=mock` must work without `MODEL_API_KEY` and without the `openai` package installed.
- On retries, send only the failing manifest and the error, never the conversation history (cost rules in DEVELOPMENT.md).
- Not used yet. Don't call the real API during this task.

### Selection
- A `get_provider()` factory reads the `PROVIDER` env var: `mock` (default) or `muse`.
- Any other value raises an error listing the valid options. Never silently fall back to mock.

## Scenario test data

In `scenarios/network-policy/`, add:
- `fix.yaml`: a correct fix (adds a NetworkPolicy that blocks the attack and keeps the app healthy).
- `fix_attempt1.yaml`: a deliberately bad first attempt that the proof step must reject (e.g. deletes the Deployment or empties the pod selector), so the anti-cheat check and the retry loop actually run.

`fix*.yaml` files are mock-only. They must never be put into a model prompt.

## Housekeeping

- Update DEVELOPMENT.md: add `agent/provider.py` to the repo layout, add `fix.yaml` / `fix_attemptN.yaml` (mock only) to the scenario format, and document the `PROVIDER`, `MUSE_MODEL` and `MUSE_BASE_URL` env vars.
- Add a `.gitignore` covering at least `.env`, `__pycache__/`, `.venv/` and `*.pyc`.

## Done when

With `PROVIDER=mock`, one command runs the network-policy scenario: confirm → fix (attempt 1 rejected by anti-cheat) → retry → fix (attempt 2 passes) → output "attack blocked, app healthy." Unit tests cover the provider factory, fence stripping and YAML validation, and the mock's attempt sequencing.

We'll switch to `PROVIDER=muse` once the key arrives.
