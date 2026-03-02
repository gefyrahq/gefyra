"""
Gradually create bridges per mount, verify traffic routing after each.

Expects the mount phase to have produced mounts and an active connection.
For each mount, create N bridges (each backed by a local container) and verify
that traffic is routed correctly.
"""

import logging
import time
from typing import List, Tuple

import httpx

from gefyra.api.bridge import create_bridge
from gefyra.api.run import run as gefyra_run
from gefyra.types import ExactMatchHeader

from tests.loadtest.helpers import MetricsCollector, kubectl_get_json, kubectl_wait, timed_step

logger = logging.getLogger("gefyra.loadtest.create_bridges")

PHASE = "create_bridges"

# The pyserver image responds with this string.
PYSERVER_MARKER = "Hello from Gefyra"
VERIFY_URL = "http://localhost:8080"
VERIFY_RETRIES = 20
VERIFY_BACKOFF = 3
# carrier2 restarts (SIGQUIT + re-exec) on each config change; give it
# time to come back before we start probing.
SETTLE_AFTER_ACTIVE_S = 5


def _verify_bridge_traffic(
    header_name: str,
    header_value: str,
    expected_content: str = PYSERVER_MARKER,
    url: str = VERIFY_URL,
) -> str | None:
    """Send a request with the given header and check the response.

    Returns None on success, or a diagnostic string on failure.
    """
    last_status = None
    last_body = ""
    for attempt in range(VERIFY_RETRIES):
        try:
            resp = httpx.get(url, headers={header_name: header_value}, timeout=10)
            last_status = resp.status_code
            last_body = resp.text[:200]
            if expected_content in resp.text:
                return None  # success
        except httpx.HTTPError as exc:
            last_body = str(exc)
        time.sleep(VERIFY_BACKOFF)
    return (
        f"{header_name}={header_value} → "
        f"status={last_status}, body={last_body!r}"
    )


def run_phase(
    metrics: MetricsCollector,
    connection_name: str,
    mount_names: List[str],
    bridges_per_mount: int,
    local_image: str,
    kubeconfig: str = "",
    local_port: int = 8000,
    remote_port: int = 80,
    delay_between: float = 0.5,
) -> List[Tuple[str, str, str]]:
    """
    For each mount, create *bridges_per_mount* bridges.

    Each bridge gets its own local container + unique header rule so traffic
    can be selectively routed.  After each bridge is added, all existing
    bridges are verified via HTTP.

    Returns list of (bridge_name, container_name, mount_name) for Phase 5.
    """
    metrics.begin_phase(PHASE)
    bridge_records: List[Tuple[str, str, str]] = []
    global_step = 0

    for mount_idx, mount_name in enumerate(mount_names):
        for bridge_idx in range(bridges_per_mount):
            global_step += 1
            container_name = f"lt-local-{mount_idx:04d}-{bridge_idx:04d}"
            bridge_name = f"lt-br-{mount_idx:04d}-{bridge_idx:04d}"
            header_value = f"peer-{mount_idx}-{bridge_idx}"

            # --- run local container ---
            with timed_step(metrics, PHASE, global_step, f"run {container_name}") as sr:
                gefyra_run(
                    image=local_image,
                    name=container_name,
                    connection_name=connection_name,
                    detach=True,
                    auto_remove=True,
                    namespace="default",
                )
                sr.detail = container_name

            # --- create bridge with header-based routing ---
            with timed_step(metrics, PHASE, global_step, f"create_bridge {bridge_name}") as sr:
                bridge = create_bridge(
                    name=bridge_name,
                    local=container_name,
                    ports={str(local_port): str(remote_port)},
                    bridge_mount_name=mount_name,
                    connection_name=connection_name,
                    rules=[[ExactMatchHeader(name="x-gefyra", value=header_value)]],
                )
                sr.detail = f"bridge={bridge.name}"

            # --- wait for bridge CR to be processed by the operator ---
            with timed_step(metrics, PHASE, global_step, f"wait bridge ACTIVE {bridge_name}") as sr:
                try:
                    kubectl_wait(
                        resource=f"gefyrabridges.gefyra.dev/{bridge_name}",
                        condition="jsonpath=.state=ACTIVE",
                        namespace="gefyra",
                        kubeconfig=kubeconfig,
                        timeout="120s",
                    )
                    sr.detail = "ACTIVE"
                except Exception:
                    # Log current bridge state for diagnostics
                    try:
                        br_json = kubectl_get_json(
                            f"gefyrabridges.gefyra.dev/{bridge_name}",
                            "gefyra", kubeconfig,
                        )
                        current_state = br_json.get("state", "UNKNOWN")
                    except Exception:
                        current_state = "FETCH_FAILED"
                    sr.success = False
                    sr.error = f"bridge stuck in {current_state}"
                    sr.detail = f"state={current_state} (expected ACTIVE)"
                    logger.warning(f"Bridge {bridge_name} not ACTIVE, state={current_state}")

            bridge_records.append((bridge_name, container_name, mount_name))

            # Let carrier2 finish its restart before probing
            time.sleep(SETTLE_AFTER_ACTIVE_S)

            # --- verify traffic for ALL existing bridges ---
            with timed_step(metrics, PHASE, global_step, f"verify traffic ({len(bridge_records)} bridges)") as sr:
                failures = {}
                for br_name, _, _ in bridge_records:
                    parts = br_name.replace("lt-br-", "").split("-")
                    hval = f"peer-{int(parts[0])}-{int(parts[1])}"
                    diag = _verify_bridge_traffic("x-gefyra", hval)
                    if diag is not None:
                        failures[br_name] = diag
                if failures:
                    detail = "; ".join(
                        f"{name}: {info}" for name, info in failures.items()
                    )
                    sr.detail = f"FAILED: {detail}"
                    sr.success = False
                    sr.error = f"{len(failures)}/{len(bridge_records)} bridges failed"
                    logger.warning(
                        f"Traffic verification failed:\n  "
                        + "\n  ".join(
                            f"{name}: {info}" for name, info in failures.items()
                        )
                    )
                else:
                    sr.detail = f"all {len(bridge_records)} bridges OK"

            logger.info(
                f"Bridge {global_step}/{len(mount_names)*bridges_per_mount}: "
                f"{bridge_name} on mount {mount_name}"
            )

            if delay_between > 0:
                time.sleep(delay_between)

    metrics.end_phase()
    return bridge_records
