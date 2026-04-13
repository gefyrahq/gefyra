#!/usr/bin/env python3
"""GO-1030 idempotency stress driver — operator-free.

Drives ``Carrier2BridgeMount._duplicate_workload()`` directly against a real
cluster workload and verifies that the shadow deployment and its duplicated
HPA never drift. Any drift (resourceVersion bump, pod UID change, container
restart, HPA spec change) would mean the idempotency layer is broken and
slow-starting workloads (JVM apps etc.) would suffer a rolling restart on
every operator reconciliation.

Unlike a real-operator stress test, this driver does not depend on a running
Gefyra operator — so it works even when Stowaway can't come up on a given
host. It calls the provider's duplication method N times in a tight loop
(default 20 × 1s); the operator-timer equivalent would be 20 × 60s.

Usage:
    # deploy a workload (+ HPA optional), then point the driver at it:
    kubectl apply -f operator/tests/fixtures/nginx.yaml
    kubectl apply -f operator/tests/fixtures/nginx_hpa.yaml   # optional
    ./idempotency_driver.py --target deploy/nginx-deployment --container nginx
    ./idempotency_driver.py --iterations 50 --interval 0.5

Prereqs:
    - kubeconfig for the target cluster is active
    - the workload (+ HPA, optional) is already applied and ready
    - PYTHONPATH includes the operator/ directory (the script adds it itself)

Exits 0 on success, 1 on drift, 2 on setup error.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "operator"))

import kubernetes  # noqa: E402


async def _noop_event(*_args, **_kwargs) -> None:
    return None


def _make_logger() -> logging.Logger:
    log = logging.getLogger("gefyra.stress")
    log.setLevel(logging.INFO)
    if not log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
        )
        log.addHandler(handler)
    log.propagate = False
    return log


def _snapshot_shadow(apps, core, target_name: str, namespace: str) -> dict:
    d = apps.read_namespaced_deployment(f"{target_name}-gefyra", namespace)
    pods = core.list_namespaced_pod(
        namespace,
        label_selector=f"app={target_name}-gefyra",
    )
    pod_state = sorted(
        (
            p.metadata.uid,
            (p.status.container_statuses[0].restart_count
             if p.status.container_statuses else 0),
        )
        for p in pods.items
    )
    return {
        "rv": d.metadata.resource_version,
        "uid": d.metadata.uid,
        "pods": pod_state,
    }


def _snapshot_hpa(autoscaling, shadow_hpa_name: str, namespace: str) -> dict:
    h = autoscaling.read_namespaced_horizontal_pod_autoscaler(
        shadow_hpa_name, namespace
    )
    return {
        "rv": h.metadata.resource_version,
        "target": h.spec.scale_target_ref.name,
        "min": h.spec.min_replicas,
        "max": h.spec.max_replicas,
    }


def _discover_shadow_hpa(autoscaling, namespace: str) -> str | None:
    hpas = autoscaling.list_namespaced_horizontal_pod_autoscaler(namespace)
    for h in hpas.items:
        if h.metadata.name.endswith("-gefyra"):
            return h.metadata.name
    return None


async def run(args) -> int:
    log = _make_logger()
    kubernetes.config.load_kube_config()

    # Imports deferred until after sys.path + kubeconfig are set up.
    from gefyra.bridge_mount.carrier2mount import Carrier2BridgeMount
    from gefyra.configuration import OperatorConfiguration

    provider = Carrier2BridgeMount(
        name="idempotency-stress",
        configuration=OperatorConfiguration(),
        target_namespace=args.namespace,
        target=args.target,
        target_container=args.container,
        post_event_function=_noop_event,
        logger=log,
    )

    apps = kubernetes.client.AppsV1Api()
    core = kubernetes.client.CoreV1Api()
    autoscaling = kubernetes.client.AutoscalingV2Api()
    target_name = args.target.split("/", 1)[1]
    shadow_name = f"{target_name}-gefyra"

    log.info(f"initial prepare() for {args.target} → {shadow_name}")
    try:
        await provider.prepare()
    except Exception as e:
        log.error(f"prepare() failed: {e}")
        return 2

    log.info("waiting for shadow deployment to become ready…")
    for _ in range(args.ready_timeout // 2):
        try:
            d = apps.read_namespaced_deployment_status(shadow_name, args.namespace)
        except kubernetes.client.ApiException as e:
            log.warning(f"shadow deployment not visible yet: {e.reason}")
            await asyncio.sleep(2)
            continue
        desired = d.spec.replicas or 1
        ready = d.status.ready_replicas or 0
        if ready >= desired:
            break
        await asyncio.sleep(2)
    else:
        log.error(f"shadow deployment did not become ready within "
                  f"{args.ready_timeout}s")
        return 2

    shadow_hpa_name = _discover_shadow_hpa(autoscaling, args.namespace)
    if shadow_hpa_name:
        log.info(f"duplicated HPA found: {shadow_hpa_name}")
    else:
        log.info("no duplicated HPA detected — running workload-only scenario")

    baseline_shadow = _snapshot_shadow(apps, core, target_name, args.namespace)
    baseline_hpa = (
        _snapshot_hpa(autoscaling, shadow_hpa_name, args.namespace)
        if shadow_hpa_name
        else None
    )
    log.info(f"baseline shadow: {baseline_shadow}")
    if baseline_hpa:
        log.info(f"baseline HPA:    {baseline_hpa}")

    drift = 0
    for i in range(1, args.iterations + 1):
        await asyncio.sleep(args.interval)
        try:
            await provider._duplicate_workload()
        except Exception as e:
            log.error(f"iteration {i}: _duplicate_workload raised: {e}")
            drift += 1
            continue

        cur_shadow = _snapshot_shadow(apps, core, target_name, args.namespace)
        cur_hpa = (
            _snapshot_hpa(autoscaling, shadow_hpa_name, args.namespace)
            if shadow_hpa_name
            else None
        )

        if cur_shadow != baseline_shadow:
            log.error(
                f"iteration {i}: SHADOW DRIFT\n"
                f"  baseline={baseline_shadow}\n"
                f"  current ={cur_shadow}"
            )
            drift += 1
        elif cur_hpa != baseline_hpa:
            log.error(
                f"iteration {i}: HPA DRIFT\n"
                f"  baseline={baseline_hpa}\n"
                f"  current ={cur_hpa}"
            )
            drift += 1
        else:
            log.info(
                f"iteration {i}/{args.iterations}: stable "
                f"(shadow rv={cur_shadow['rv']}, "
                f"hpa rv={cur_hpa['rv'] if cur_hpa else '-'})"
            )

    if not args.skip_cleanup:
        log.info("cleanup: uninstall()")
        try:
            await provider.uninstall()
        except Exception as e:
            log.warning(f"uninstall failed (non-fatal): {e}")

    if drift:
        log.error(f"FAIL: drift observed in {drift} iteration(s)")
        return 1
    log.info(f"OK: {args.iterations} reconcile calls against real cluster, no drift")
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--target", default="deploy/nginx-deployment",
                   help="K8s workload reference (deploy/NAME or sts/NAME)")
    p.add_argument("--namespace", default="default")
    p.add_argument("--container", default="nginx",
                   help="container name inside the target pod")
    p.add_argument("--iterations", type=int, default=20)
    p.add_argument("--interval", type=float, default=1.0,
                   help="seconds between _duplicate_workload() calls")
    p.add_argument("--ready-timeout", type=int, default=240,
                   help="seconds to wait for the shadow to become ready")
    p.add_argument("--skip-cleanup", action="store_true",
                   help="leave the shadow deployment in place after the run")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(asyncio.run(run(_parse_args())))
