import logging
from pathlib import Path

# from time import sleep
from kubernetes.client import ApiException

from gefyra.api.utils import (
    random_string,
    stopwatch,
)  # get_workload_information
from gefyra.configuration import ClientConfiguration
from gefyra.exceptions import GefyraBridgeError
from gefyra.local.bridge import get_all_containers, get_gefyrabridge
from gefyra.local.mount import get_gefyrabridgemount
from gefyra.types import ExactMatchHeader, GefyraBridge, GefyraLocalContainer
from gefyra.types.bridge import PrefixMatchHeader, RegexMatchHeader
from gefyra.types.bridge_mount import GefyraBridgeMount  # , CommandTimeoutError

logger = logging.getLogger(__name__)


@stopwatch
def create_bridge(
    name: str,
    local: str,
    ports: dict,
    bridge_mount_name: str,
    handle_probes: bool = True,
    timeout: int = 0,
    wait: bool = False,
    connection_name: str = "",
    rules: list[list[ExactMatchHeader | PrefixMatchHeader | RegexMatchHeader]]
    | None = None,
) -> "GefyraBridge":
    """
    Create a GefyraBridge object
    :param name: The requested name for this GefyraBridge object
    :param local: The name of the local running container, target of the traffic
    :param ports: Mapping remote ports to local ports
    :param bridge_mount_name: The name of the GefyraBridgeMount that is target of that GefyraBridge
    :param handle_probes: (Legacy) Handle probes on this Pod
    :param connection_name: The name of the local connection to set this bridge up for
    :param rules: The rules to match traffic

    :return: The GefyraBridge object that was created.
    """
    from docker.errors import NotFound

    # from gefyra.local.bridge import get_all_gefyrabridges
    from gefyra.configuration import ClientConfiguration
    from gefyra.exceptions import GefyraBridgeMountNotFound
    from gefyra.local.bridge import (
        handle_create_gefyrabridge,
    )

    if rules is None:
        rules = []
    config = ClientConfiguration(connection_name=connection_name)

    try:
        container = config.DOCKER.containers.get(local)
    except NotFound:
        raise GefyraBridgeError(f"Could not find local target container '{local}'")

    port_mappings = [f"{key}:{value}" for key, value in ports.items()]

    try:
        local_container_ip = container.attrs["NetworkSettings"]["Networks"][
            config.NETWORK_NAME
        ]["IPAddress"]
    except KeyError:
        raise GefyraBridgeError(
            f"The target container '{local}' is not in Gefyra's network"
            f" {config.NETWORK_NAME}. Did you set up a connection for it?"
        ) from None

    try:
        mount = get_gefyrabridgemount(
            config=config,
            name=bridge_mount_name,
        )
        bridge_mount = GefyraBridgeMount(config, mount)
    except (GefyraBridgeMountNotFound, KeyError, TypeError):
        raise GefyraBridgeError(
            f"Could not find GefyraBridgeMount '{bridge_mount_name}'"
        )

    if not local_container_ip:
        raise GefyraBridgeError(
            f"Could not resolve IP address for container '{local}' in network '{config.NETWORK_NAME}'"
        )

    if not name:
        bridge_name = f"{config.CLIENT_ID[:25]}-{bridge_mount.target[:20].replace('/', '-')}-{bridge_mount.target_container[:20]}-{random_string(5)}"
    else:
        bridge_name = name
    if len(bridge_name) > 63:
        raise RuntimeError(
            "The name of the GefyraBridge must be no more than 63 characters"
        )

    logger.debug(f"Creating GefyraBridge for GefyraBridgeMount: {bridge_mount_name}")

    bridge_body = GefyraBridge(
        name=bridge_name,
        local_container_ip=local_container_ip,
        local_container_name=local,
        port_mappings=port_mappings,
        target=bridge_mount_name,
        rules=rules,
        client=config.CLIENT_ID,
    ).get_k8s_bridge_body(config)

    bridge = handle_create_gefyrabridge(config, bridge_body, bridge_mount_name)
    logger.debug(f"Bridge {bridge['metadata']['name']} created")
    #
    # block until all bridges are in place
    #
    logger.debug("Waiting for the bridge(s) to become active")
    return GefyraBridge.from_raw(bridge, config)


def wait_for_deletion(
    gefyra_bridges: list, config: "ClientConfiguration", timeout: int = 60
):
    from kubernetes.watch import Watch

    w = Watch()
    deleted = []
    uids = [gefyra_bridge["metadata"]["uid"] for gefyra_bridge in gefyra_bridges]
    for event in w.stream(
        config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object,
        namespace=config.NAMESPACE,
        group="gefyra.dev",
        version="v1",
        plural="gefyrabridges",
        timeout_seconds=timeout,
        _request_timeout=timeout,
    ):
        if event["type"] == "DELETED" and event["object"]["metadata"]["uid"] in uids:
            deleted.append(event["object"]["metadata"]["uid"])
            if set(deleted) == set(uids):
                return True


@stopwatch
def delete_bridge(
    name: str | None = None,
    mount_name: str | None = None,
    connection_name: str = "",
    wait: bool = False,
    timeout: int | None = 60,
) -> bool:
    from gefyra.configuration import ClientConfiguration
    from gefyra.local.bridge import handle_delete_gefyrabridge

    config = ClientConfiguration(connection_name=connection_name)
    if name:
        gefyra_bridge = handle_delete_gefyrabridge(config, name)
        if gefyra_bridge:
            if wait:
                success = wait_for_deletion(
                    [gefyra_bridge], config=config, timeout=timeout
                )
                if not success:
                    raise TimeoutError("Timeout for this operation reached.")
            logger.info(f"Bridge {name} removed")
        return gefyra_bridge
    elif mount_name:
        bridges = config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object(
            "gefyra.dev",
            "v1",
            config.NAMESPACE,
            "gefyrabridges",
            label_selector=f"gefyra.dev/bridge-mount={mount_name}",
        )
        if not bridges["items"]:
            raise RuntimeError(
                f"No GefyraBridge found for GefyraBridgeMount {mount_name} or GefyraBridgeMount does not exist."
            )
        for bridge in bridges["items"]:
            gefyra_bridge = handle_delete_gefyrabridge(
                config, bridge["metadata"]["name"]
            )
            if gefyra_bridge:
                if wait:
                    success = wait_for_deletion([gefyra_bridge], config=config)
                    if not success:
                        raise TimeoutError("Timeout for this operation reached.")
                logger.info(f"Bridge {bridge['metadata']['name']} removed")
    return True


@stopwatch
def unbridge_all(
    wait: bool = False,
    connection_name: str = "",
) -> bool:
    from gefyra.configuration import ClientConfiguration
    from gefyra.local.bridge import (
        get_all_gefyrabridges,
        handle_delete_gefyrabridge,
    )

    config = ClientConfiguration(connection_name=connection_name)

    gefyra_bridges = get_all_gefyrabridges(config)
    for gefyra_bridge in gefyra_bridges:
        name = gefyra_bridge["metadata"]["name"]
        logger.info(f"Removing Bridge {name}")
        handle_delete_gefyrabridge(config, name)
    if wait:
        success = wait_for_deletion(config=config, gefyra_bridges=gefyra_bridges)
        if not success:
            raise TimeoutError("Timeout for this operation reached.")
    return True


@stopwatch
def list_bridges(
    kubeconfig: Path | None = None,
    kubecontext: str | None = None,
    connection_name: str = "",
    filter_client: bool = True,
    get_containers: bool = False,
) -> list[tuple[GefyraLocalContainer | None, GefyraBridge]]:
    """
    Retrieve all GefyraBridge objects
    """

    config = ClientConfiguration(
        kube_config_file=kubeconfig,
        kube_context=kubecontext,
        connection_name=connection_name,
    )
    try:
        bridges = config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object(
            namespace=config.NAMESPACE,
            group="gefyra.dev",
            plural="gefyrabridges",
            version="v1",
            label_selector=(
                f"gefyra.dev/client={config.CLIENT_ID}" if filter_client else None
            ),
        )
    except ApiException as e:
        raise RuntimeError(
            f"Cannot list GefyraBridges: {e}Is Gefyra installed and running in this cluster?"
        ) from None
    if get_containers:
        all_containers = get_all_containers(config=config)
        all_bridges = [
            GefyraBridge.from_raw(raw_bridge, config) for raw_bridge in bridges["items"]
        ]
        result = []
        for bridge in all_bridges:
            for container in all_containers:
                if container.address == bridge.local_container_ip:
                    result.append(
                        (
                            container,
                            bridge,
                        )
                    )
                    break
                else:
                    continue
            else:
                result.append((None, bridge))
        return result
    else:
        return [
            (None, GefyraBridge.from_raw(raw_bridge, config))
            for raw_bridge in bridges["items"]
        ]


@stopwatch
def get_bridge(
    bridge_name: str,
    connection_name: str = "",
    kubeconfig: Path | None = None,
    kubecontext: str | None = None,
    resolve_container: bool = True,
) -> GefyraBridge:
    """
    Get a GefyraBridge object
    """
    config_params = {"connection_name": connection_name}
    if kubeconfig:
        config_params.update({"kube_config_file": str(kubeconfig)})

    if kubecontext:
        config_params.update({"kube_context": kubecontext})
    config = ClientConfiguration(**config_params)  # type: ignore
    bridge = get_gefyrabridge(config, bridge_name)
    gefyra_bridge = GefyraBridge.from_raw(bridge, config)
    if resolve_container and config.CLIENT_ID:  # only set with active connection
        gefyra_bridge.resolve_local_container(config)
    return gefyra_bridge
