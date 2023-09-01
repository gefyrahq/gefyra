import logging
from time import sleep
from typing import List, Dict, TYPE_CHECKING

from gefyra.exceptions import CommandTimeoutError, GefyraBridgeError

if TYPE_CHECKING:
    from gefyra.configuration import ClientConfiguration
    from gefyra.types import GefyraBridge


from .utils import stopwatch, wrap_bridge

logger = logging.getLogger(__name__)


def get_pods_to_intercept(
    workload_name: str, workload_type: str, namespace: str, config
) -> Dict[str, List[str]]:
    from gefyra.cluster.resources import (
        get_pods_and_containers_for_pod_name,
        get_pods_and_containers_for_workload,
    )

    pods_to_intercept = {}
    if workload_type != "pod":
        pods_to_intercept.update(
            get_pods_and_containers_for_workload(
                config, workload_name, namespace, workload_type
            )
        )
    else:
        pods_to_intercept.update(
            get_pods_and_containers_for_pod_name(config, workload_name, namespace)
        )
    return pods_to_intercept


def check_workloads(
    pods_to_intercept,
    workload_type: str,
    workload_name: str,
    container_name: str,
    namespace: str,
    config,
):
    from gefyra.cluster.resources import check_pod_valid_for_bridge

    pod_names = pods_to_intercept.keys()
    if len(pod_names) == 0:
        raise Exception("Could not find any pod to bridge.")

    cleaned_names = ["-".join(name.split("-")[:-2]) for name in pod_names]

    if workload_type != "pod" and workload_name not in cleaned_names:
        raise RuntimeError(
            f"Could not find {workload_type}/{workload_name} to bridge. Available"
            f" {workload_type}: {', '.join(cleaned_names)}"
        )
    if container_name not in [
        container for c_list in pods_to_intercept.values() for container in c_list
    ]:
        raise RuntimeError(f"Could not find container {container_name} to bridge.")

    for name in pod_names:
        check_pod_valid_for_bridge(config, name, namespace, container_name)


@stopwatch
def bridge(
    name: str,
    ports: dict,
    target: str,
    namespace: str = "default",
    handle_probes: bool = True,
    timeout: int = 0,
    wait: bool = False,
    connection_name: str = "",
) -> List["GefyraBridge"]:
    from docker.errors import NotFound
    from gefyra.local.bridge import get_all_gefyrabridges
    from gefyra.configuration import ClientConfiguration

    config = ClientConfiguration(connection_name=connection_name)

    try:
        container = config.DOCKER.containers.get(name)
    except NotFound:
        raise GefyraBridgeError(f"Could not find target container '{name}'")

    port_mappings = [f"{key}:{value}" for key, value in ports.items()]

    try:
        local_container_ip = container.attrs["NetworkSettings"]["Networks"][
            config.NETWORK_NAME
        ]["IPAddress"]
    except KeyError:
        raise GefyraBridgeError(
            f"The target container '{name}' is not in Gefyra's network"
            f" {config.NETWORK_NAME}. Did you run 'gefyra up'?"
        ) from None

    try:
        _bits = list(filter(None, target.split("/")))
        workload_type, workload_name = _bits[0:2]
        container_name = _bits[2] if _bits[2:] else None
    except IndexError:
        raise GefyraBridgeError(
            "Invalid --target notation. Use"
            " <workload_type>/<workload_name>(/<container_name>)."
        ) from None

    pods_to_intercept = get_pods_to_intercept(
        workload_name=workload_name,
        workload_type=workload_type,
        namespace=namespace,
        config=config,
    )
    if not container_name:
        container_name = pods_to_intercept[list(pods_to_intercept.keys())[0]][0]

    ireq_base_name = f"{name}-to-{namespace}.{workload_type}.{workload_name}"

    check_workloads(
        pods_to_intercept,
        workload_type=workload_type,
        workload_name=workload_name,
        container_name=container_name,
        namespace=namespace,
        config=config,
    )

    if len(pods_to_intercept.keys()) > 1:
        use_index = True
    else:
        use_index = False

    from gefyra.local.bridge import (
        get_gbridge_body,
        handle_create_gefyrabridge,
    )

    ireqs = []
    for idx, pod in enumerate(pods_to_intercept):
        logger.info(f"Creating bridge for Pod {pod}")
        ireq_body = get_gbridge_body(
            config,
            name=f"{ireq_base_name}-{idx}" if use_index else ireq_base_name,
            destination_ip=local_container_ip,
            target_pod=pod,
            target_namespace=namespace,
            target_container=container_name,
            port_mappings=port_mappings,
            handle_probes=handle_probes,
        )
        ireq = handle_create_gefyrabridge(config, ireq_body, target)
        logger.debug(f"Bridge {ireq['metadata']['name']} created")
        ireqs.append(ireq)
    #
    # block until all bridges are in place
    #
    logger.info("Waiting for the bridge(s) to become active")

    bridges = {str(ireq["metadata"]["uid"]): False for ireq in ireqs}
    waiting_time = 0
    # timeout = 0  means no timeout
    if timeout:
        waiting_time = timeout
    while True and wait:
        # watch whether all relevant bridges have been established
        gefyra_bridges = get_all_gefyrabridges(config)
        for gefyra_bridge in gefyra_bridges:
            if (
                gefyra_bridge["metadata"]["uid"] in bridges.keys()
                and gefyra_bridge.get("state", "") == "ACTIVE"
            ):
                bridges[str(gefyra_bridge["metadata"]["uid"])] = True
                logger.info(
                    f"Bridge {gefyra_bridge['metadata']['name']} "
                    f"({sum(bridges.values())}/{len(ireqs)}) established."
                )
        if all(bridges.values()):
            break
        sleep(1)
        # Raise exception in case timeout is reached
        waiting_time -= 1
        if timeout and waiting_time <= 0:
            raise CommandTimeoutError("Timeout for bridging operation exceeded")
    if not wait:
        gefyra_bridges = get_all_gefyrabridges(config)
        return list(map(wrap_bridge, gefyra_bridges))
    else:
        logger.info("Following bridges have been established:")
        _bridges = list(map(wrap_bridge, gefyra_bridges))
        for gefyra_bridge in gefyra_bridges:
            for port in port_mappings:
                (
                    pod_name,
                    ns,
                ) = (
                    gefyra_bridge["targetPod"],
                    gefyra_bridge["targetNamespace"],
                )
                bridge_ports = port.split(":")
                container_port, pod_port = bridge_ports[0], bridge_ports[1]
                logger.info(
                    f"Bridge for pod {pod_name} in namespace {ns} on port {pod_port} "
                    f"to local container {container_name} on port {container_port}"
                )
        return _bridges


def wait_for_deletion(gefyra_bridges: List, config: "ClientConfiguration"):
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
    ):
        if event["type"] == "DELETED":
            if event["object"]["metadata"]["uid"] in uids:
                deleted.append(event["object"]["metadata"]["uid"])
                if set(deleted) == set(uids):
                    break


@stopwatch
def unbridge(
    name: str,
    connection_name: str = "",
    wait: bool = False,
) -> bool:
    from gefyra.local.bridge import handle_delete_gefyrabridge
    from gefyra.configuration import ClientConfiguration

    config = ClientConfiguration(connection_name=connection_name)

    gefyra_bridge = handle_delete_gefyrabridge(config, name)
    if gefyra_bridge:
        if wait:
            wait_for_deletion([gefyra_bridge], config=config)
        logger.info(f"Bridge {name} removed")
    return True


@stopwatch
def unbridge_all(
    wait: bool = False,
    connection_name: str = "",
) -> bool:
    from gefyra.configuration import ClientConfiguration
    from gefyra.local.bridge import (
        handle_delete_gefyrabridge,
        get_all_gefyrabridges,
    )

    config = ClientConfiguration(connection_name=connection_name)

    gefyra_bridges = get_all_gefyrabridges(config)
    for gefyra_bridge in gefyra_bridges:
        name = gefyra_bridge["metadata"]["name"]
        logger.info(f"Removing Bridge {name}")
        handle_delete_gefyrabridge(config, name)
    if wait:
        wait_for_deletion(config=config, gefyra_bridges=gefyra_bridges)
    return True
