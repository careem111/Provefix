#!/usr/bin/env bash
# Health: the worker pod is Running and its sleep process is alive. Exit 0 = healthy.
source "$(dirname "$0")/../_lib/probe.sh"
phase=$(k get pod -l app=worker -o jsonpath='{.items[0].status.phase}' 2>/dev/null)
[ "$phase" = "Running" ] || { echo "pod not Running (phase: ${phase:-none})"; exit 1; }
k exec deploy/worker -- sh -c \
  'for d in /proc/[0-9]*/cmdline; do grep -qa "sleep 3600" "$d" 2>/dev/null && exit 0; done; exit 1' \
  && { echo "worker process alive"; exit 0; }
echo "worker process not found"
exit 1
