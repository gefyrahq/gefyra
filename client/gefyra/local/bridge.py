import logging
from time import sleep
from typing import Dict, List, Optional

from docker.models.containers import Container

from gefyra.configuration import ClientConfiguration
from gefyra.local.cargo import get_cargo_ip_from_netaddress
from gefyra.types import GefyraLocalContainer

from .utils import handle_docker_run_container

logger = logging.getLogger(__name__)


def handle_create_gefyrabridge(config: ClientConfiguration, body, target: str):
    from kubernetes.client import ApiException

    try:
        ireq = config.K8S_CUSTOM_OBJECT_API.create_namespaced_custom_object(
            namespace=config.NAMESPACE,
            body=body,
            group="gefyra.dev",
            plural="gefyrabridges",
            version="v1",
        )
    except ApiException as e:
        if e.status == 409:
            raise RuntimeError(f"Workload {target} already bridged.")
        logger.error(
            f"A Kubernetes API Error occured. \nReason: {e.reason} \nBody: {e.body}"
        )
        raise e from None
    return ireq


def handle_delete_gefyrabridge(config: ClientConfiguration, name: str) -> bool:
    from kubernetes.client import ApiException

    try:
        ireq = config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object(
            namespace=config.NAMESPACE,
            name=name,
            group="gefyra.dev",
            plural="gefyrabridges",
            version="v1",
        )
        return ireq
    except ApiException as e:
        if e.status == 404:
            logger.debug(f"InterceptRequest {name} not found")
        else:
            logger.debug("Error removing InterceptRequest: " + str(e))
        return False


def get_all_gefyrabridges(config: ClientConfiguration) -> list:
    from kubernetes.client import ApiException

    try:
        ireq_list = config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object(
            namespace=config.NAMESPACE,
            group="gefyra.dev",
            plural="gefyrabridges",
            version="v1",
        )
        if ireq_list:
            # filter bridges for this client
            return list(
                item
                for item in ireq_list.get("items")
                if item["client"] == config.CLIENT_ID
            )
        else:
            return []
    except ApiException as e:
        if e.status != 404:
            logger.warning("Error getting GefyraBridges: " + str(e))
            raise e from None
        return []


def get_all_containers(config: ClientConfiguration) -> List[GefyraLocalContainer]:
    container_information = []
    gefyra_net = config.DOCKER.networks.get(f"{config.NETWORK_NAME}")
    containers = gefyra_net.containers
    # filter out gefyra-cargo container as well as fields other than name and ip
    for container in containers:
        if not container.name.startswith("gefyra-cargo"):
            container_information.append(
                GefyraLocalContainer(
                    name=container.name,
                    address=container.attrs["NetworkSettings"]["Networks"][
                        config.NETWORK_NAME
                    ]["IPAddress"].split("/")[0],
                    namespace=container.attrs["HostConfig"]["DnsSearch"][0].split(".")[
                        0
                    ],
                )
            )
    return container_information


def get_gbridge_body(
    config: ClientConfiguration,
    name: str,
    destination_ip,
    target_pod,
    target_namespace,
    target_container,
    port_mappings,
    handle_probes,
):
    return {
        "apiVersion": "gefyra.dev/v1",
        "kind": "gefyrabridge",
        "metadata": {
            "name": name,
            "namespace": config.NAMESPACE,
        },
        "provider": "carrier",
        "connectionProvider": "stowaway",
        "client": config.CLIENT_ID,
        "destinationIP": destination_ip,
        "targetPod": target_pod,
        "targetNamespace": target_namespace,
        "targetContainer": target_container,
        "portMappings": port_mappings,
        "handleProbes": handle_probes,
    }


def deploy_app_container(
    config: ClientConfiguration,
    image: str,
    name: str = "",
    command: str = "",
    volumes: Optional[List] = None,
    ports: Optional[Dict] = None,
    env: Optional[Dict] = None,
    auto_remove: bool = False,
    dns_search: Optional[List[str]] = None,
) -> Container:
    import docker

    if not dns_search:
        dns_search = ["default"]

    gefyra_net = config.DOCKER.networks.get(f"{config.NETWORK_NAME}")

    net_add = gefyra_net.attrs["IPAM"]["Config"][0]["Subnet"].split("/")[0]
    cargo_ip = get_cargo_ip_from_netaddress(net_add)
    all_kwargs = {
        "network": config.NETWORK_NAME,
        "name": name,
        "command": command,
        "volumes": volumes,
        "ports": ports,
        "detach": True,
        "dns": [config.STOWAWAY_IP],
        "dns_search": dns_search,
        "auto_remove": auto_remove,
        "environment": env,
        "pid_mode": f"container:{config.CARGO_CONTAINER_NAME}",  # noqa: E231
    }
    not_none_kwargs = {k: v for k, v in all_kwargs.items() if v is not None}

    container = handle_docker_run_container(config, image, **not_none_kwargs)

    cargo = config.DOCKER.containers.get(config.CARGO_CONTAINER_NAME)

    # busy wait for the container to start
    try:
        _i = 0
        while container.status == "created" and _i < (
            config.CONTAINER_RUN_TIMEOUT * 10
        ):
            sleep(0.1)
            container = config.DOCKER.containers.get(container.id)
            _i = _i + 1
    except docker.errors.NotFound:
        raise RuntimeError(
            f"Container {container.id} is not running. Did you miss a valid startup"
            " command?"
        )

    if container.status != "running":
        raise RuntimeError(
            "Container is not running. Did you miss a valid startup command?"
        )

    exit_code, output = cargo.exec_run(
        f"bash patchContainerGateway.sh {container.name} {cargo_ip}"
    )
    if exit_code == 0:
        logger.debug(f"Gateway patch applied to '{container.name}'")

    else:
        container = config.DOCKER.containers.get(container.id)
        if container.status != "running":
            raise RuntimeError(
                f"Container {name} is not running. Check whether your command is valid"
                " for the chosen image."
            )
        raise RuntimeError(
            f"Gateway patch could not be applied to '{container.name}': {output}"
        )
    return container
