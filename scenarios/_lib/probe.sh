# Shared helpers for scenario scripts. Source it; expects NS and KUBE_CONTEXT.
set -u
k() { kubectl --context "${KUBE_CONTEXT:-kind-provefix}" -n "$NS" "$@"; }

# fetch_from_pod <pod-name> <labels> <url>
# Starts a one-shot busybox pod with <labels> that tries to fetch <url> a few times.
# Exit 0 if any try succeeded. The pod is deleted afterwards.
fetch_from_pod() {
  local name="$1-$RANDOM" labels="$2" url="$3" phase=""
  k run "$name" --image=busybox:1.36 --image-pull-policy=IfNotPresent --restart=Never \
    --labels="$labels" --command -- \
    sh -c "for i in 1 2 3 4 5; do wget -qO- -T 2 '$url' && exit 0; sleep 2; done; echo 'could not reach $url'; exit 1" >/dev/null
  for _ in $(seq 1 45); do
    phase=$(k get pod "$name" -o jsonpath='{.status.phase}' 2>/dev/null)
    case "$phase" in Succeeded|Failed) break ;; esac
    sleep 1
  done
  k logs "$name" 2>/dev/null
  k delete pod "$name" --wait=false >/dev/null 2>&1
  [ "$phase" = "Succeeded" ]
}
