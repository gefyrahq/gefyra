"""
Gradually remove all bridges, verifying that traffic routing
still works for the remaining bridges after each removal.
"""

import logging
import time
from typing import List, Tuple

import docker

from gefyra.api.bridge import delete_bridge

from tests.loadtest.helpers import MetricsCollector, timed_step
from tests.loadtest.phases.phase_create_bridges import _verify_bridge_traffic

logger = logging.getLogger("gefyra.loadtest.remove_bridges")

PHASE = "remove_bridges"


def run_phase(
    metrics: MetricsCollector,
    bridge_records: List[Tuple[str, str, str]],
    connection_name: str,
    delay_between: float = 0.5,
):
    """
    Remove bridges one-by-one.  After each removal, verify that all
    *remaining* bridges still route traffic correctly.

    bridge_records: list of (bridge_name, container_name, mount_name) from Phase 4.
    """
    metrics.begin_phase(PHASE)
    docker_client = docker.from_env()
    remaining = list(bridge_records)
    total = len(remaining)

    for i in range(total):
        bridge_name, container_name, mount_name = remaining.pop(0)
        step = i + 1

        # --- delete bridge ---
        with timed_step(metrics, PHASE, step, f"delete_bridge {bridge_name}") as sr:
            delete_bridge(
                name=bridge_name,
                connection_name=connection_name,
                wait=True,
            )
            sr.detail = bridge_name

        # --- stop local container ---
        with timed_step(metrics, PHASE, step, f"stop container {container_name}") as sr:
            try:
                c = docker_client.containers.get(container_name)
                if c.status == "running":
                    c.stop()
                c.remove()
            except (docker.errors.NotFound, docker.errors.APIError):
                pass  # auto_remove containers may already be gone
            sr.detail = container_name

        # --- verify remaining bridges still work ---
        if remaining:
            with timed_step(metrics, PHASE, step, f"verify traffic ({len(remaining)} remaining)") as sr:
                failures = {}
                for br_name, _, _ in remaining:
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
                    sr.error = f"{len(failures)}/{len(remaining)} bridges failed"
                    logger.warning(
                        f"Traffic verification failed for remaining bridges:\n  "
                        + "\n  ".join(
                            f"{name}: {info}" for name, info in failures.items()
                        )
                    )
                else:
                    sr.detail = f"all {len(remaining)} remaining bridges OK"

        logger.info(
            f"Bridge {step}/{total} removed: {bridge_name} "
            f"({len(remaining)} remaining, all verified)"
        )

        if delay_between > 0 and remaining:
            time.sleep(delay_between)

    metrics.end_phase()
