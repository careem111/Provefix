#!/usr/bin/env bash
# Health: the api can still reach the database. Exit 0 = app healthy.
source "$(dirname "$0")/../_lib/probe.sh"
k exec deploy/api -- sh -c \
  'for i in 1 2 3 4 5; do wget -qO- -T 2 http://db:8080/health.txt && exit 0; sleep 2; done; exit 1'
