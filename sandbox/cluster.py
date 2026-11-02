"""Sandbox runner: the only code that touches the cluster.

Every kubectl call is pinned to the kind context, and manifests are refused if
they could reach outside the sandbox namespace.
"""
import os
import secrets
import subprocess
from contextlib import contextmanager

import yaml

CONTEXT = os.environ.get("KUBE_CONTEXT", "kind-provefix")
TIMEOUT = 60

# Namespaced kinds a scenario manifest may create. Cluster-scoped kinds are refused.
ALLOWED_KINDS = {
    "ConfigMap", "Deployment", "StatefulSet", "DaemonSet", "Pod", "Service",
    "ServiceAccount", "Role", "RoleBinding", "NetworkPolicy", "Secret",
}


class SandboxError(RuntimeError):
    pass


def run(cmd, timeout=TIMEOUT, input=None, env=None):
    """Run a command. A timeout returns exit code 124 instead of raising."""
    try:
        return subprocess.run(cmd, input=input, capture_output=True, text=True, timeout=timeout,
                              env={**os.environ, **(env or {})})
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(cmd, 124, _text(e.stdout), _text(e.stderr) + f"\ntimed out after {timeout}s")


def _text(b):
    return b.decode(errors="replace") if isinstance(b, bytes) else (b or "")


def describe(proc):
    """Everything needed to debug a step: what ran, exit code, stdout, stderr."""
    cmd = " ".join(proc.args) if isinstance(proc.args, list) else str(proc.args)
    return f"$ {cmd}\nexit code: {proc.returncode}\nstdout:\n{proc.stdout.rstrip()}\nstderr:\n{proc.stderr.rstrip()}"


def kubectl(*args, timeout=TIMEOUT, input=None):
    return run(["kubectl", "--context", CONTEXT, *args], timeout=timeout, input=input)


def preflight():
    """Refuse to run unless we're on a kind cluster with Calico enforcing NetworkPolicies."""
    if not CONTEXT.startswith("kind-"):
        raise SandboxError(f"KUBE_CONTEXT={CONTEXT!r} is not a kind cluster; ProveFix only runs on kind")
    proc = kubectl("get", "pods", "-n", "kube-system", "-l", "k8s-app=calico-node",
                   "-o", "jsonpath={.items[*].status.phase}")
    if proc.returncode != 0:
        raise SandboxError("cannot reach the sandbox cluster\n" + describe(proc))
    phases = proc.stdout.split()
    if not phases or any(p != "Running" for p in phases):
        raise SandboxError(f"Calico is not running (calico-node phases: {phases or 'none'}); "
                           "NetworkPolicy results can't be trusted")


def validate_manifest(text):
    """Return a list of reasons this manifest must not be applied (empty = safe)."""
    errors = []
    for doc in yaml.safe_load_all(text):
        if doc is None:
            continue
        kind = doc.get("kind")
        name = (doc.get("metadata") or {}).get("name")
        if kind not in ALLOWED_KINDS:
            errors.append(f"{kind}/{name}: kind not allowed in the sandbox")
        if (doc.get("metadata") or {}).get("namespace"):
            errors.append(f"{kind}/{name}: sets metadata.namespace; manifests must stay in the sandbox")
    return errors


def create_namespace(prefix):
    ns = f"pf-{prefix}-{secrets.token_hex(3)}"
    proc = kubectl("create", "namespace", ns)
    if proc.returncode != 0:
        raise SandboxError("could not create sandbox namespace\n" + describe(proc))
    return ns


def delete_namespace(ns):
    kubectl("delete", "namespace", ns, "--wait=false", "--ignore-not-found")


@contextmanager
def sandbox(prefix):
    """A fresh namespace that's deleted afterwards, whatever happens."""
    ns = create_namespace(prefix)
    try:
        yield ns
    finally:
        delete_namespace(ns)


def apply(ns, text, timeout=TIMEOUT):
    """Apply a manifest into ns and wait for its Deployments. Returns (passed, detail)."""
    errors = validate_manifest(text)
    if errors:
        return False, "refused to apply:\n" + "\n".join(errors)
    proc = kubectl("apply", "-n", ns, "-f", "-", input=text)
    if proc.returncode != 0:
        return False, describe(proc)
    deployments = kubectl("get", "deployments", "-n", ns, "-o", "name")
    if deployments.stdout.strip():
        proc = kubectl("wait", "-n", ns, "--for=condition=Available", "deployment", "--all",
                       f"--timeout={timeout}s", timeout=timeout + 10)
        if proc.returncode != 0:
            return False, "deployments did not become available\n" + describe(proc)
    return True, "applied"


def run_script(path, ns, timeout=TIMEOUT):
    """Run a scenario script against ns. The script sees NS and KUBE_CONTEXT."""
    return run(["bash", str(path)], timeout=timeout, env={"NS": ns, "KUBE_CONTEXT": CONTEXT})
