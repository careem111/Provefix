"""Fix providers: where a corrected manifest comes from.

PROVIDER=mock (default) reads canned fixes from the scenario folder.
PROVIDER=muse calls Muse Spark through the Meta Model API.
"""
import os
from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path

from agent.fixer import build_messages, clean_fix

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_MODEL = "muse-spark-1.1"
DEFAULT_BASE_URL = "https://api.meta.ai/v1"
MAX_TOKENS = 3000
DEFAULT_REASONING_EFFORT = "low"  # lowest that works; reasoning is billed as output


class FixProvider(ABC):
    def generate_fix(self, finding, manifest, exploit_output=None, last_error=None) -> str:
        """Return a corrected manifest as a YAML string. Raises ValueError if the reply isn't YAML."""
        return clean_fix(self._raw_fix(finding, manifest, exploit_output, last_error))

    @abstractmethod
    def _raw_fix(self, finding, manifest, exploit_output, last_error) -> str:
        """Return the provider's raw reply (may still contain Markdown fences)."""


class MockFixProvider(FixProvider):
    """Returns fix_attemptN.yaml on attempt N if present, else fix.yaml. Never calls the API."""

    def __init__(self):
        self._attempts = defaultdict(int)

    def _raw_fix(self, finding, manifest, exploit_output, last_error):
        self._attempts[finding["id"]] += 1
        n = self._attempts[finding["id"]]
        folder = scenario_dir(finding)
        candidates = [folder / f"fix_attempt{n}.yaml", folder / "fix.yaml"]
        for path in candidates:
            if path.is_file():
                return path.read_text()
        raise FileNotFoundError(
            f"MockFixProvider: no fix for attempt {n} in {folder} "
            f"(looked for {', '.join(p.name for p in candidates)})"
        )


class MuseSparkProvider(FixProvider):
    """Calls Muse Spark via the OpenAI-compatible Meta Model API. The client is created on first use."""

    def __init__(self):
        self.model = os.environ.get("MUSE_MODEL", DEFAULT_MODEL)
        self.base_url = os.environ.get("MUSE_BASE_URL", DEFAULT_BASE_URL)
        self.reasoning_effort = os.environ.get("MUSE_REASONING_EFFORT") or DEFAULT_REASONING_EFFORT
        self._client = None

    def _get_client(self):
        if self._client is None:
            api_key = os.environ.get("MODEL_API_KEY")
            if not api_key:
                raise RuntimeError("MODEL_API_KEY is not set; PROVIDER=muse needs it")
            from openai import OpenAI

            self._client = OpenAI(base_url=self.base_url, api_key=api_key)
        return self._client

    def _raw_fix(self, finding, manifest, exploit_output, last_error):
        resp = self._get_client().chat.completions.create(
            model=self.model,
            messages=build_messages(finding, manifest, exploit_output, last_error),
            max_tokens=MAX_TOKENS,
            reasoning_effort=self.reasoning_effort,
        )
        return resp.choices[0].message.content


PROVIDERS = {"mock": MockFixProvider, "muse": MuseSparkProvider}


def get_provider(name=None) -> FixProvider:
    name = (name or os.environ.get("PROVIDER") or "mock").strip().lower()
    if name not in PROVIDERS:
        raise ValueError(f"unknown PROVIDER {name!r}; valid options: {', '.join(PROVIDERS)}")
    return PROVIDERS[name]()


def scenario_dir(finding) -> Path:
    path = Path(finding["manifest_path"])
    if not path.is_absolute():
        path = ROOT / path
    return path.parent
