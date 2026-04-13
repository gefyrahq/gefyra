#!/usr/bin/env bash
# GO-1030 idempotency stress-test.
#
# Verifies that repeated operator reconciliations do NOT:
#   - bump the shadow deployment's resourceVersion (= no apiserver write)
#   - rotate shadow pods (same pod UIDs, same restart count)
#   - change the duplicated HPA's spec
#
# Prerequisite: a Gefyra operator is running, the source workload + (optional)
# HPA are deployed, and a GefyraBridgeMount targeting the workload has reached
# ACTIVE state. By default the script targets the nginx fixture from
# operator/tests/fixtures/nginx.yaml + nginx_hpa.yaml — override via the env
# variables below for any other workload.
#
#   testing/stress/idempotency_stress.sh [--iterations N] [--interval SECONDS]
#
# Defaults: 5 iterations, 70 seconds apart (operator reconcile loop runs
# every 60s; 70s makes sure we observe at least one full cycle).
#
# Override the targeted resources via env vars:
#   NS=default SHADOW=foo-gefyra ORIGINAL_HPA=foo-hpa SHADOW_HPA=foo-hpa-gefyra \
#     testing/stress/idempotency_stress.sh
#
# Exits non-zero on any drift.

set -euo pipefail

NS="${NS:-default}"
SHADOW="${SHADOW:-nginx-deployment-gefyra}"
ORIGINAL_HPA="${ORIGINAL_HPA:-nginx-deployment-hpa}"
SHADOW_HPA="${SHADOW_HPA:-nginx-deployment-hpa-gefyra}"

iterations=5
interval=70

while [[ $# -gt 0 ]]; do
  case "$1" in
    --iterations) iterations="$2"; shift 2 ;;
    --interval)   interval="$2";   shift 2 ;;
    -h|--help)
      sed -n '2,18p' "$0"; exit 0 ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

log() { printf '%s %s\n' "[$(date -u +%H:%M:%S)]" "$*"; }

snapshot() {
  local kind="$1" name="$2" jsonpath="$3"
  kubectl -n "$NS" get "$kind" "$name" -o jsonpath="$jsonpath" 2>/dev/null
}

shadow_snapshot() {
  # "<rv>|<uid>|<podUid1>:<restart1>,<podUid2>:<restart2>,..."
  local rv uid pods
  rv=$(snapshot deploy "$SHADOW" '{.metadata.resourceVersion}')
  uid=$(snapshot deploy "$SHADOW" '{.metadata.uid}')
  pods=$(kubectl -n "$NS" get pods \
    -l "app=$(snapshot deploy "$SHADOW" '{.spec.selector.matchLabels.app}')" \
    -o jsonpath='{range .items[*]}{.metadata.uid}:{.status.containerStatuses[0].restartCount},{end}' \
    2>/dev/null || true)
  printf '%s|%s|%s' "$rv" "$uid" "$pods"
}

hpa_snapshot() {
  # "<rv>|<scaleTargetName>|<min>|<max>"
  local rv target min max
  rv=$(snapshot hpa "$SHADOW_HPA" '{.metadata.resourceVersion}')
  target=$(snapshot hpa "$SHADOW_HPA" '{.spec.scaleTargetRef.name}')
  min=$(snapshot hpa "$SHADOW_HPA" '{.spec.minReplicas}')
  max=$(snapshot hpa "$SHADOW_HPA" '{.spec.maxReplicas}')
  printf '%s|%s|%s|%s' "$rv" "$target" "$min" "$max"
}

if ! kubectl -n "$NS" get deploy "$SHADOW" >/dev/null 2>&1; then
  echo "Shadow deployment '$SHADOW' not found in namespace '$NS'." >&2
  echo "Apply testing/workloads/slow_java_stress.yaml first and wait for ACTIVE." >&2
  exit 2
fi

baseline_shadow=$(shadow_snapshot)
baseline_hpa=$(hpa_snapshot || true)

log "baseline shadow   : $baseline_shadow"
log "baseline shadow HPA: ${baseline_hpa:-<not present>}"

fail=0
for i in $(seq 1 "$iterations"); do
  log "iteration $i/$iterations — waiting ${interval}s for reconcile tick"
  sleep "$interval"

  current_shadow=$(shadow_snapshot)
  if [[ "$current_shadow" != "$baseline_shadow" ]]; then
    log "DRIFT in shadow deployment:"
    log "  baseline: $baseline_shadow"
    log "  current : $current_shadow"
    fail=1
  else
    log "shadow stable (rv=${baseline_shadow%%|*})"
  fi

  if [[ -n "$baseline_hpa" ]]; then
    current_hpa=$(hpa_snapshot)
    if [[ "$current_hpa" != "$baseline_hpa" ]]; then
      log "DRIFT in duplicated HPA:"
      log "  baseline: $baseline_hpa"
      log "  current : $current_hpa"
      fail=1
    else
      log "shadow HPA stable (rv=${baseline_hpa%%|*})"
    fi
  fi
done

if [[ "$fail" -ne 0 ]]; then
  log "FAIL: drift observed during reconciliations — idempotency broken"
  exit 1
fi

log "OK: $iterations reconcile ticks, no drift on shadow or HPA."
