"""Builds the Muse Spark prompt and cleans up the model's reply."""
import json
import re

import yaml

SYSTEM_PROMPT = (
    "You fix Kubernetes security issues. Return only valid YAML, no prose. "
    "Return the complete corrected manifest: keep every existing resource, "
    "do not change Deployment or Service selectors, and do not set metadata.namespace."
)

_FENCE = re.compile(r"```(?:ya?ml)?[ \t]*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def build_messages(finding, manifest, exploit_output=None, last_error=None):
    """Build the chat messages for one fix request.

    `manifest` is always the original vulnerable manifest, never a previous fix:
    a failed fix may have deleted resources, and the model can't restore what it
    can't see. On a retry (last_error set) the finding, the original manifest and
    the last error are sent, never the earlier conversation — that keeps token
    cost flat across attempts.
    """
    user = f"Finding:\n{json.dumps(finding, indent=2)}\n\nManifest:\n{manifest}\n"
    if last_error:
        user += (
            f"\nYour previous fix for this manifest failed verification:\n{last_error}\n"
            "\nStart again from the manifest above and return a corrected manifest."
        )
    else:
        if exploit_output:
            user += f"\nThis attack currently succeeds against the manifest:\n{exploit_output}\n"
        user += "\nReturn the corrected manifest so the attack is blocked and the app keeps working."
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def clean_fix(text):
    """Strip Markdown fences and check the result is a YAML manifest. Raises ValueError."""
    if text is None or not text.strip():
        raise ValueError("fix is empty")
    m = _FENCE.search(text)
    body = (m.group(1) if m else text).strip()
    try:
        docs = [d for d in yaml.safe_load_all(body) if d is not None]
    except yaml.YAMLError as e:
        raise ValueError(f"fix is not valid YAML: {e}") from e
    if not docs:
        raise ValueError("fix contains no YAML documents")
    for d in docs:
        if not isinstance(d, dict) or "kind" not in d:
            raise ValueError(f"fix contains a document that is not a Kubernetes object: {str(d)[:80]!r}")
    return body + "\n"
