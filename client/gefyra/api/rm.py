"""
Remove local Gefyra containers and their associated GefyraBridge CRDs.

When a local container is removed via `docker rm`, the GefyraBridge CRD in
Kubernetes is not cleaned up — the Carrier sidecar keeps intercepting traffic
and routing it to a dead destination. This module provides `rm()` and `rm_all()`
which first delete any matching bridges (by matching the container's IP against
the bridge's `destinationIP`), then remove the container.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gefyra.configuration import ClientConfiguration

from .utils import stopwatch

logger = logging.getLogger(__name__)


def _get_bridges_for_container(
    config: "ClientConfiguration", container_ip: str
) -> list:
    from gefyra.local.bridge import get_all_gefyrabridges

    gefyra_bridges = get_all_gefyrabridges(config)
    return [
        bridge
        for bridge in gefyra_bridges
        if bridge.get("destinationIP") == container_ip
    ]


@stopwatch
def rm(
    name: str,
    connection_name: str = "",
    wait: bool = False,
    force: bool = False,
) -> bool:
    from docker.errors import NotFound
    from gefyra.configuration import ClientConfiguration
    from gefyra.local.bridge import handle_delete_gefyrabridge
    from gefyra.api.bridge import wait_for_deletion

    config = ClientConfiguration(connection_name=connection_name)

    try:
        container = config.DOCKER.containers.get(name)
    except NotFound:
        raise RuntimeError(f"Could not find container '{name}'") from None

    try:
        container_ip = container.attrs["NetworkSettings"]["Networks"][
            config.NETWORK_NAME
        ]["IPAddress"]
    except KeyError:
        container_ip = None

    if container_ip:
        matching_bridges = _get_bridges_for_container(config, container_ip)
        for bridge in matching_bridges:
            bridge_name = bridge["metadata"]["name"]
            logger.info(f"Removing bridge {bridge_name}")
            handle_delete_gefyrabridge(config, bridge_name)
        if wait and matching_bridges:
            wait_for_deletion(matching_bridges, config=config)
    else:
        matching_bridges = []

    logger.info(f"Removing container {name}")
    container.remove(force=force)

    if matching_bridges:
        logger.info(
            f"Removed {len(matching_bridges)} bridge(s) and container '{name}'"
        )
    else:
        logger.info(f"Removed container '{name}' (no bridges found)")
    return True


@stopwatch
def rm_all(
    connection_name: str = "",
    wait: bool = False,
    force: bool = False,
) -> bool:
    from gefyra.configuration import ClientConfiguration
    from gefyra.local.bridge import get_all_containers

    config = ClientConfiguration(connection_name=connection_name)
    containers = get_all_containers(config)

    if not containers:
        logger.info("No Gefyra containers found")
        return True

    for container_info in containers:
        rm(
            name=container_info.name,
            connection_name=connection_name,
            wait=wait,
            force=force,
        )
    return True
