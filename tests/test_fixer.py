import pytest

from agent.fixer import build_messages, clean_fix

GOOD = "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: x\n"


@pytest.mark.parametrize("reply", [
    GOOD,
    f"```yaml\n{GOOD}```",
    f"```\n{GOOD}```",
    f"Here is the fix:\n\n```YAML\n{GOOD}```\nThis blocks the attack.",
])
def test_clean_fix_strips_fences(reply):
    assert clean_fix(reply) == GOOD


def test_clean_fix_allows_multiple_documents():
    assert clean_fix(f"{GOOD}---\n{GOOD}").count("kind: ConfigMap") == 2


@pytest.mark.parametrize("reply, match", [
    ("", "empty"),
    (None, "empty"),
    ("kind: [unclosed", "not valid YAML"),
    ("---\n", "no YAML documents"),
    ("Sure! I fixed it.", "not a Kubernetes object"),
])
def test_clean_fix_rejects_bad_replies(reply, match):
    with pytest.raises(ValueError, match=match):
        clean_fix(reply)


def test_first_prompt_includes_finding_and_exploit():
    msgs = build_messages({"id": "f1"}, GOOD, exploit_output="customer-records")
    assert '"id": "f1"' in msgs[1]["content"]
    assert "customer-records" in msgs[1]["content"]


def test_retry_prompt_sends_original_manifest_and_error():
    msgs = build_messages({"id": "f1"}, GOOD, exploit_output="customer-records", last_error="smoke failed")
    user = msgs[1]["content"]
    assert "smoke failed" in user and GOOD in user and '"id": "f1"' in user
    assert "customer-records" not in user
    assert len(msgs) == 2
