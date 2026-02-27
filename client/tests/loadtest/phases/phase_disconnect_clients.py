"""
Gradually disconnect all clients.
"""

import logging
import time
from typing import List, Tuple

from gefyra.api.connect import disconnect, remove_connection

from tests.loadtest.helpers import MetricsCollector, timed_step

logger = logging.getLogger("gefyra.loadtest.disconnect_clients")

PHASE = "disconnect_clients"


def run_phase(
    metrics: MetricsCollector,
    connections: List[Tuple[str, str]],
    delay_between: float = 0.5,
):
    """
    Disconnect and remove all connections one-by-one.
    """
    metrics.begin_phase(PHASE)
    total = len(connections)

    for i, (client_id, connection_name) in enumerate(connections):
        step = i + 1

        # --- disconnect ---
        with timed_step(metrics, PHASE, step, f"disconnect {connection_name}") as sr:
            try:
                disconnect(connection_name=connection_name)
                sr.detail = connection_name
            except Exception:
                logger.exception(f"Failed to disconnect {connection_name}")
                raise

        # --- remove connection (cleanup cargo container + network) ---
        with timed_step(metrics, PHASE, step, f"remove_connection {connection_name}") as sr:
            try:
                remove_connection(connection_name=connection_name)
                sr.detail = connection_name
            except Exception:
                logger.exception(f"Failed to remove connection {connection_name}")
                raise

        logger.info(f"Client {step}/{total} disconnected: {connection_name}")

        if delay_between > 0 and i < total - 1:
            time.sleep(delay_between)

    metrics.end_phase()
