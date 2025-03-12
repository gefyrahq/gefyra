import logging
from time import sleep

from gefyra.api.utils import get_workload_information
from gefyra.exceptions import CommandTimeoutError
from gefyra.local.mount import (
    get_all_gefyrabridgemounts,
    get_gbridgemount_body,
    handle_create_gefyrabridgemount,
)

logger = logging.getLogger(__name__)


def mount(
    namespace: str,
    target: str,
    provider: str,
    provider_parameter: dict[str, str],
    connection_name: str = "",
    wait: bool = False,
    timeout: int = 0,
):
    from gefyra.configuration import ClientConfiguration

    config = ClientConfiguration(connection_name=connection_name)
    workload_type, workload_name, container_name = get_workload_information(target)
    bridge_mount_body = get_gbridgemount_body(
        config, target, target, namespace, container_name
    )
    bridge_mount = handle_create_gefyrabridgemount(config, bridge_mount_body, target)

    if timeout:
        waiting_time = timeout
    while True and wait:
        # watch whether all relevant bridges have been established
        mounts = get_all_gefyrabridgemounts(config)
        for mount in mounts:
            if (
                mount["metadata"]["uid"] in bridge_mount["metadata"]["uid"]
                and mount.get("state", "") == "ACTIVE"
            ):
                logger.info(f"Bridge mount {mount['metadata']['name']} established.")
                break
        sleep(1)
        # Raise exception in case timeout is reached
        waiting_time -= 1
        if timeout and waiting_time <= 0:
            raise CommandTimeoutError("Timeout for bridging operation exceeded")
    return True
