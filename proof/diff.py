"""Anti-cheat: reject fixes that 'pass' by deleting or detaching the app."""
import yaml

WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet"}


def _index(text):
    return {(d.get("kind"), (d.get("metadata") or {}).get("name")): d
            for d in yaml.safe_load_all(text) if d}


def _selector(doc):
    spec = doc.get("spec") or {}
    if doc["kind"] == "Service":
        return spec.get("selector") or {}
    return (spec.get("selector") or {}).get("matchLabels") or {}


def check(original, fixed):
    """Returns (passed, detail)."""
    before, after = _index(original), _index(fixed)
    problems = []
    for (kind, name), doc in before.items():
        if kind not in WORKLOAD_KINDS | {"Service"}:
            continue
        if (kind, name) not in after:
            problems.append(f"{kind}/{name} was deleted")
            continue
        old, new = _selector(doc), _selector(after[(kind, name)])
        if not new:
            problems.append(f"{kind}/{name} selector was emptied")
        elif new != old:
            problems.append(f"{kind}/{name} selector changed from {old} to {new}")
    if problems:
        return False, "anti-cheat: " + "; ".join(problems)
    return True, "all workloads and services kept with the same selectors"
