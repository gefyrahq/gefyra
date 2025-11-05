import logging
from pathlib import Path
import random
import string

# from time import sleep
from typing import List, Dict, TYPE_CHECKING, Optional, Tuple

from gefyra.local.bridge import get_all_containers, get_gefyrabridge
from gefyra.types import ExactMatchHeader, GefyraLocalContainer
from gefyra.local.mount import get_gefyrabridgemount
from gefyra.exceptions import GefyraBridgeError
from gefyra.types.bridge_mount import GefyraBridgeMount  # , CommandTimeoutError
from gefyra.types import GefyraBridge
from gefyra.configuration import ClientConfiguration


from gefyra.api.utils import (
    random_string,
    stopwatch,
    wrap_bridge,
)  # get_workload_information

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
    pods_to_intercept: dict,
    workload_type: str,
    workload_name: str,
    container_name: str,
    namespace: str,
    config: "ClientConfiguration",
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

    # Validate workload and probes
    api = config.K8S_APP_API
    core_api = config.K8S_CORE_API
    try:
        reconstructed_workload_type = get_workload_type(workload_type)
        if reconstructed_workload_type == "pod":
            workload = core_api.read_namespaced_pod(workload_name, namespace)
        elif reconstructed_workload_type == "deployment":
            workload = api.read_namespaced_deployment(workload_name, namespace)
        elif reconstructed_workload_type == "statefulset":
            workload = api.read_namespaced_stateful_set(workload_name, namespace)
    except ApiException as e:
        raise RuntimeError(
            f"Error fetching workload {workload_type}/{workload_name}: {e}"
        )

    containers = (
        workload.spec.template.spec.containers
        if hasattr(workload.spec, "template")
        else workload.spec.containers
    )
    target_container = next((c for c in containers if c.name == container_name), None)
    if not target_container:
        raise RuntimeError(
            f"Container {container_name} not found in workload {workload_type}/{workload_name}."
        )

    def validate_http_probe(probe, probe_type):
        if probe and probe.http_get is None:
            raise RuntimeError(
                f"{probe_type} in container {container_name} does not use httpGet. "
                f"Only HTTP-based probes are supported."
            )

    # Check for HTTP probes only
    validate_http_probe(target_container.liveness_probe, "LivenessProbe")
    validate_http_probe(target_container.readiness_probe, "ReadinessProbe")
    validate_http_probe(target_container.startup_probe, "StartupProbe")

    for name in pod_names:
        check_pod_valid_for_bridge(config, name, namespace, container_name)


@stopwatch
def create_bridge(
    name: str,
    ports: dict,
    bridge_mount_name: str,
    handle_probes: bool = True,
    timeout: int = 0,
    wait: bool = False,
    connection_name: str = "",
    match_header: List[ExactMatchHeader] = [],
) -> "GefyraBridge":
    """
    Create a GefyraBridge object
    :param name: The name of the local running container, target of the traffic
    :param ports: Mapping remote ports to local ports
    :param bridge_mount_name: The name of the GefyraBridgeMount that is target of that GefyraBridge
    :param handle_probes: (Legacy) Handle probes on this Pod
    :param connection_name: The name of the local connection to set this bridge up for
    :param match_header: A list of rules to match and intercept traffic

    :return: The GefyraBridge object that was created.
    """
    from docker.errors import NotFound

    # from gefyra.local.bridge import get_all_gefyrabridges
    from gefyra.configuration import ClientConfiguration
    from gefyra.local.bridge import (
        handle_create_gefyrabridge,
    )

    config = ClientConfiguration(connection_name=connection_name)

    try:
        container = config.DOCKER.containers.get(name)
    except NotFound:
        raise GefyraBridgeError(f"Could not find local target container '{name}'")

    port_mappings = [f"{key}:{value}" for key, value in ports.items()]

    try:
        local_container_ip = container.attrs["NetworkSettings"]["Networks"][
            config.NETWORK_NAME
        ]["IPAddress"]
    except KeyError:
        raise GefyraBridgeError(
            f"The target container '{name}' is not in Gefyra's network"
            f" {config.NETWORK_NAME}. Did you set up a connection for it?"
        ) from None

    try:
        mount = get_gefyrabridgemount(
            config=config,
            name=bridge_mount_name,
        )
        bridge_mount = GefyraBridgeMount(config, mount)
    except Exception as e:
        raise GefyraBridgeError(
            f"Could not find GefyraBridgeMount '{bridge_mount_name}'"
        )

    bridge_name = f"{config.CLIENT_ID[:25]}-{bridge_mount.target[:20]}-{bridge_mount.target_container[:20]}-{random_string(5)}"
    if len(bridge_name) > 63:
        raise RuntimeError(
            "The name of the GefyraBridge must be no more than 63 characters"
        )

    logger.debug(f"Creating GefyraBridge for GefyraBridgeMount: {bridge_mount_name}")

    bridge_body = GefyraBridge(
        name=bridge_name,
        local_container_ip=local_container_ip,
        port_mappings=port_mappings,
        target=bridge_mount_name,
        exact_match_headers=match_header,
        client=config.CLIENT_ID,
    ).get_k8s_bridge_body(config)

    bridge = handle_create_gefyrabridge(config, bridge_body, bridge_mount_name)
    logger.debug(f"Bridge {bridge['metadata']['name']} created")
    #
    # block until all bridges are in place
    #
    logger.debug("Waiting for the bridge(s) to become active")
    return GefyraBridge.from_raw(bridge, config)


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
def delete_bridge(
    name: Optional[str] = None,
    mount_name: Optional[str] = None,
    connection_name: str = "",
    wait: bool = False,
) -> bool:
    from gefyra.local.bridge import handle_delete_gefyrabridge
    from gefyra.configuration import ClientConfiguration

    config = ClientConfiguration(connection_name=connection_name)
    if name:
        gefyra_bridge = handle_delete_gefyrabridge(config, name)
        if gefyra_bridge:
            if wait:
                wait_for_deletion([gefyra_bridge], config=config)
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
        for bridge in bridges["items"]:
            gefyra_bridge = handle_delete_gefyrabridge(
                config, bridge["metadata"]["name"]
            )
            if gefyra_bridge:
                if wait:
                    wait_for_deletion([gefyra_bridge], config=config)
                logger.info(f"Bridge {bridge['metadata']['name']} removed")
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


@stopwatch
def list_bridges(
    kubeconfig: Optional[Path] = None,
    kubecontext: Optional[str] = None,
    connection_name: str = "",
    filter_client: bool = True,
    get_containers: bool = False,
) -> List[GefyraBridge] | List[Tuple[GefyraLocalContainer | None, GefyraBridge]]:
    """
    Retrieve all GefyraBridge objects
    """
    from kubernetes.client import ApiException

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
                    result.append(None, bridge)
        return result
    else:
        return [
            GefyraBridge.from_raw(raw_bridge, config) for raw_bridge in bridges["items"]
        ]


@stopwatch
def get_bridge(
    bridge_name: str,
    connection_name: str = "",
    kubeconfig: Optional[Path] = None,
    kubecontext: Optional[str] = None,
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
    return GefyraBridge.from_raw(bridge, config)
