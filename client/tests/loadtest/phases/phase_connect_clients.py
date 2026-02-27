"""
Gradually connect N clients, verifying each one after connect.
"""

import fcntl
import logging
import os
import socket
import struct
import time
from pathlib import Path
from typing import List, Tuple

import docker

from gefyra.api.clients import add_clients, get_client, write_client_file
from gefyra.api.connect import connect
from gefyra.api.status import status, StatusSummary
from gefyra.configuration import get_gefyra_config_location
from gefyra.types.client import GefyraClientState

from tests.loadtest.helpers import MetricsCollector, timed_step

logger = logging.getLogger("gefyra.loadtest.connect_clients")

PHASE = "connect_clients"


def _get_docker0_ip() -> str:
    """Get the docker0 bridge IP — reachable from cargo containers and where k3d maps ports."""
    _soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(
        fcntl.ioctl(
            _soc.fileno(), 0x8915,
            struct.pack("256s", "docker0".encode("utf-8")[:15]),
        )[20:24]
    )


def _cleanup_stale_cargo_containers():
    """Remove leftover cargo containers from previous loadtest runs."""
    client = docker.from_env()
    containers = client.containers.list(
        all=True, filters={"name": "gefyra-cargo-lt-"}
    )
    for c in containers:
        logger.info(f"  Removing stale cargo container: {c.name}")
        c.remove(force=True)
    # Also clean up gefyra config files from previous runs
    config_dir = Path(get_gefyra_config_location())
    if config_dir.exists():
        for f in config_dir.glob("lt-*"):
            logger.debug(f"  Removing stale config file: {f}")
            f.unlink()
        for f in config_dir.glob("lt-*"):
            f.unlink()


def run_phase(
    metrics: MetricsCollector,
    num_clients: int,
    delay_between: float = 1.0,
    cargo_image: str = "",
    kubeconfig: str = "",
) -> List[Tuple[str, str]]:
    """
    Connect *num_clients* clients one-by-one.

    Returns a list of (client_id, connection_name) tuples for use in later phases.
    """
    metrics.begin_phase(PHASE)
    connections: List[Tuple[str, str]] = []

    logger.info("Cleaning up stale cargo containers from previous runs ...")
    _cleanup_stale_cargo_containers()

    for i in range(num_clients):
        client_id = f"lt-client-{i:04d}"
        connection_name = f"lt-conn-{i:04d}"
        step = i + 1

        kube_path = Path(kubeconfig) if kubeconfig else None

        # --- create client CR ---
        with timed_step(metrics, PHASE, step, f"add_client {client_id}") as sr:
            try:
                clients = add_clients(
                    client_id=client_id, quantity=1, kubeconfig=kube_path,
                )
                sr.detail = f"client_id={clients[0].client_id}"
            except Exception:
                logger.exception(f"Failed to add client {client_id}")
                raise

        # --- wait for client to be provisioned ---
        with timed_step(metrics, PHASE, step, f"wait_for_client {client_id}") as sr:
            gclient = get_client(client_id, kubeconfig=kube_path)
            gclient.wait_for_state(GefyraClientState.WAITING, timeout=120)
            sr.detail = f"state={gclient.state}"

        # --- write client file ---
        with timed_step(metrics, PHASE, step, f"write_client_file {client_id}") as sr:
            client_json = write_client_file(
                client_id=client_id,
                host=_get_docker0_ip(),
                kubeconfig=kube_path,
            )
            file_loc = os.path.join(
                get_gefyra_config_location(),
                f"{client_id}_client.json",
            )
            with open(file_loc, "w") as fh:
                fh.write(client_json)
            sr.detail = file_loc

        # --- connect ---
        with timed_step(metrics, PHASE, step, f"connect {connection_name}") as sr:
            with open(file_loc, "r") as fh:
                connect(
                    connection_name=connection_name,
                    client_config=fh,
                    kubeconfig=kube_path,
                    cargo_image=cargo_image or None,
                )
            sr.detail = connection_name

        # --- verify ---
        with timed_step(metrics, PHASE, step, f"verify {connection_name}") as sr:
            s = status(connection_name=connection_name)
            if s.summary != StatusSummary.UP:
                raise AssertionError(
                    f"Expected status UP for {connection_name}, got {s.summary}"
                )
            if not s.client.cargo:
                raise AssertionError(f"Cargo not running for {connection_name}")
            if not s.client.connection:
                raise AssertionError(f"Connection not active for {connection_name}")
            sr.detail = f"summary={s.summary}"

        connections.append((client_id, connection_name))
        logger.info(f"Client {step}/{num_clients} connected: {connection_name}")

        if delay_between > 0 and i < num_clients - 1:
            time.sleep(delay_between)

    metrics.end_phase()
    return connections
