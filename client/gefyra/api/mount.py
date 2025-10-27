import logging
from pathlib import Path
from time import sleep
from typing import List, Optional

from gefyra.api.utils import get_workload_information, random_string, stopwatch
from gefyra.configuration import ClientConfiguration
from gefyra.exceptions import CommandTimeoutError
from gefyra.local.mount import (
    get_gefyrabridgemount,
    get_gbridgemount_body,
    handle_create_gefyrabridgemount,
    handle_delete_gefyramount,
)
from gefyra.types import GefyraBridgeMount

logger = logging.getLogger(__name__)


def mount(
    namespace: str,
    target: str,
    provider: str,
    kubeconfig: Path,
    kubecontext: str,
    connection_name: str = "",
    wait: bool = False,
    timeout: int = 0,
    mount_name: str | None = None,
    tls_certificate: Optional[str] = None,
    tls_key: Optional[str] = None,
    tls_sni: Optional[str] = None,
):
    from gefyra.configuration import ClientConfiguration

    config = ClientConfiguration(
        kube_config_file=kubeconfig,
        kube_context=kubecontext,
        connection_name=connection_name,
    )
    _, workload_name, container_name = get_workload_information(target)
    if not mount_name:
        mount_name = f"{workload_name[:25]}-{namespace[:20]}-{random_string(5)}"
    bridge_mount_body = get_gbridgemount_body(
        config,
        mount_name,
        workload_name,
        namespace,
        container_name,
        tls_certificate,
        tls_key,
        tls_sni,
    )
    bridge_mount = handle_create_gefyrabridgemount(config, bridge_mount_body, target)
    waiting_time = 0
    if timeout:
        waiting_time = timeout
    while True and wait:
        # watch whether all relevant mounts have been established
        mount = get_gefyrabridgemount(config, mount_name)
        if mount.uid in bridge_mount["metadata"]["uid"] and mount._state == "ACTIVE":
            logger.info(f"Bridge mount {mount.name} established.")
            break
        sleep(1)
        # Raise exception in case timeout is reached
        waiting_time -= 1
        if timeout and waiting_time <= 0:
            raise CommandTimeoutError("Timeout for bridging operation exceeded")
    return bridge_mount


@stopwatch
def get_mount(
    mount_name: str,
    connection_name: str = "",
    kubeconfig: Optional[Path] = None,
    kubecontext: Optional[str] = None,
) -> GefyraBridgeMount:
    """
    Get a GefyraBridgeMount object
    """
    config_params = {"connection_name": connection_name}
    if kubeconfig:
        config_params.update({"kube_config_file": str(kubeconfig)})

    if kubecontext:
        config_params.update({"kube_context": kubecontext})
    config = ClientConfiguration(**config_params)  # type: ignore
    mount = get_gefyrabridgemount(config, mount_name)
    return GefyraBridgeMount(mount)


@stopwatch
def delete_mount(
    mount_name: str,
    force: bool = False,
    kubeconfig: Optional[Path] = None,
    kubecontext: Optional[str] = None,
    connection_name: Optional[str] = None,
    wait: bool = False,
) -> bool:
    """
    Delete a GefyraClient configuration
    """
    config = ClientConfiguration(
        kube_config_file=kubeconfig,
        kube_context=kubecontext,
        connection_name=connection_name if connection_name else "no-connection-name",
        # use no-connection-name to make sure you use admin access to the cluster
    )
    return handle_delete_gefyramount(config, mount_name, force, wait=wait)


@stopwatch
def list_mounts(
    kubeconfig: Optional[Path] = None, kubecontext: Optional[str] = None
) -> List[GefyraBridgeMount]:
    """
    List all GefyraBridgeMount objects
    """
    from kubernetes.client import ApiException

    config = ClientConfiguration(kube_config_file=kubeconfig, kube_context=kubecontext)
    try:
        bridge_mounts = config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object(
            namespace=config.NAMESPACE,
            group="gefyra.dev",
            plural="gefyrabridgemounts",
            version="v1",
        )
    except ApiException as e:
        logger.error(f"Error listing GefyraBridgeMounts: {e}")
        exit(1)
    return [GefyraBridgeMount(bridge_mount) for bridge_mount in bridge_mounts["items"]]
