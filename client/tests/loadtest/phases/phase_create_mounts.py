"""
Quickly create N mounts against the target workload.

Connects a dedicated client, then creates mounts that will be used by
the bridge phase.
"""

import logging
import os
import time
from pathlib import Path
from typing import List, Tuple

from gefyra.api.clients import add_clients, get_client, write_client_file
from gefyra.api.connect import connect
from gefyra.api.mount import create_mount
from gefyra.api.status import status, StatusSummary
from gefyra.configuration import get_gefyra_config_location
from gefyra.types.client import GefyraClientState

from tests.loadtest.helpers import (
    MetricsCollector,
    kubectl_wait,
    timed_step,
)
from tests.loadtest.phases.phase_connect_clients import _get_docker0_ip

logger = logging.getLogger("gefyra.loadtest.create_mounts")

PHASE = "create_mounts"


def _ensure_connected(
    metrics: MetricsCollector,
    kubeconfig: str,
    cargo_image: str = "",
) -> Tuple[str, str]:
    """Make sure we have one active connection for mount/bridge phases."""
    client_id = "lt-mount-client"
    connection_name = "lt-mount-conn"
    kube_path = Path(kubeconfig) if kubeconfig else None

    with timed_step(metrics, PHASE, 0, "add_client for mounts") as sr:
        add_clients(client_id=client_id, quantity=1, kubeconfig=kube_path)
        sr.detail = client_id

    with timed_step(metrics, PHASE, 0, "wait_for_client for mounts") as sr:
        gclient = get_client(client_id, kubeconfig=kube_path)
        gclient.wait_for_state(GefyraClientState.WAITING, timeout=120)

    with timed_step(metrics, PHASE, 0, "write_client_file for mounts") as sr:
        client_json = write_client_file(
            client_id=client_id, host=_get_docker0_ip(), kubeconfig=kube_path,
        )
        file_loc = os.path.join(
            get_gefyra_config_location(), f"{client_id}_client.json"
        )
        with open(file_loc, "w") as fh:
            fh.write(client_json)

    with timed_step(metrics, PHASE, 0, "connect for mounts") as sr:
        with open(file_loc, "r") as fh:
            connect(
                connection_name=connection_name,
                client_config=fh,
                kubeconfig=kube_path,
                cargo_image=cargo_image or None,
            )

    with timed_step(metrics, PHASE, 0, "verify connection for mounts") as sr:
        s = status(connection_name=connection_name)
        if s.summary != StatusSummary.UP:
            raise AssertionError(f"Expected UP, got {s.summary}")

    return client_id, connection_name


def run_phase(
    metrics: MetricsCollector,
    num_mounts: int,
    workload_target: str,
    workload_namespace: str,
    kubeconfig: str,
    kubecontext: str = "",
    cargo_image: str = "",
) -> Tuple[str, str, List[str]]:
    """
    Create *num_mounts* GefyraBridgeMounts.

    Returns (client_id, connection_name, list_of_mount_names).
    """
    metrics.begin_phase(PHASE)

    client_id, connection_name = _ensure_connected(
        metrics, kubeconfig, cargo_image=cargo_image,
    )

    mount_names: List[str] = []

    for i in range(num_mounts):
        step = i + 1
        mount_name = f"lt-mount-{i:04d}"

        with timed_step(metrics, PHASE, step, f"create_mount {mount_name}") as sr:
            mount = create_mount(
                namespace=workload_namespace,
                target=workload_target,
                kubeconfig=Path(kubeconfig),
                kubecontext=kubecontext or None,
                connection_name=connection_name,
                wait=True,
                timeout=120,
                mount_name=mount_name,
            )
            sr.detail = f"mount={mount.name}, state={mount._state}"

        # verify CR reached ACTIVE
        with timed_step(metrics, PHASE, step, f"verify mount {mount_name}") as sr:
            kubectl_wait(
                resource=f"gefyrabridgemounts.gefyra.dev/{mount_name}",
                condition="jsonpath=.state=ACTIVE",
                namespace="gefyra",
                kubeconfig=kubeconfig,
                timeout="120s",
            )
            sr.detail = "ACTIVE"

        mount_names.append(mount_name)
        logger.info(f"Mount {step}/{num_mounts} created: {mount_name}")

    metrics.end_phase()
    return client_id, connection_name, mount_names
