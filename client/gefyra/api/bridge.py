import logging
from datetime import datetime
from time import sleep
from typing import List, Dict

from gefyra.cluster.resources import get_pods_and_containers_for_workload
from gefyra.configuration import default_configuration
from gefyra.local.bridge import get_all_interceptrequests

from .utils import stopwatch

logger = logging.getLogger(__name__)


def get_pods_to_intercept(
    deployment: str, namespace: str, statefulset: str, pod: str, config
) -> Dict[str, List[str]]:
    from gefyra.cluster.resources import get_pods_and_containers_for_pod_name

    pods_to_intercept = {}
    if deployment:
        pods_to_intercept.update(
            get_pods_and_containers_for_workload(
                config, deployment, namespace, "deployment"
            )
        )
    if statefulset:
        pods_to_intercept.update(
            get_pods_and_containers_for_workload(
                config, statefulset, namespace, "statefulset"
            )
        )
    if pod:
        pods_to_intercept.update(
            get_pods_and_containers_for_pod_name(config, pod, namespace)
        )
    return pods_to_intercept


def check_workloads(pods_to_intercept, deployment, statefulset, container_name):
    if len(pods_to_intercept.keys()) == 0:
        raise Exception("Could find any pod to bridge.")
    elif len(pods_to_intercept.keys()) > 1:
        use_index = True
    else:
        use_index = False

    cleaned_names = ["-".join(key.split("-")[:-2]) for key in pods_to_intercept.keys()]

    if deployment and deployment not in cleaned_names:
        raise RuntimeError(
            f"Could not find deployment {deployment} to bridge. Available deployments:"
            f" {', '.join(cleaned_names)}"
        )
    if statefulset and statefulset not in cleaned_names:
        raise RuntimeError(
            f"Could not find statefulset {statefulset} to bridge. Available statefulsets:"
            f" {', '.join(cleaned_names)}"
        )
    if container_name not in [
        container for c_list in pods_to_intercept.values() for container in c_list
    ]:
        raise RuntimeError(f"Could not find container {container_name} to bridge.")
    return use_index


@stopwatch
def bridge(
    name: str,
    ports: dict,
    deployment: str = None,
    statefulset: str = None,
    pod: str = None,
    container_name: str = None,
    namespace: str = "default",
    bridge_name: str = None,
    sync_down_dirs: List[str] = None,
    handle_probes: bool = True,
    timeout: int = 0,
    config=default_configuration,
) -> bool:
    from docker.errors import NotFound
    from gefyra.local.utils import set_gefyra_network_from_cargo

    config = set_gefyra_network_from_cargo(config)

    try:
        container = config.DOCKER.containers.get(name)
    except NotFound:
        logger.error(f"Could not find target container '{name}'")
        return False

    ports = [f"{key}:{value}" for key, value in ports.items()]

    try:
        local_container_ip = container.attrs["NetworkSettings"]["Networks"][
            config.NETWORK_NAME
        ]["IPAddress"]
    except KeyError:
        logger.error(
            f"The target container '{name}' is not in Gefyra's network {config.NETWORK_NAME}."
            f" Did you run 'gefyra up'?"
        )
        return False

    pods_to_intercept = get_pods_to_intercept(
        deployment=deployment,
        statefulset=statefulset,
        namespace=namespace,
        pod=pod,
        config=config,
    )

    if not bridge_name:
        ireq_base_name = (
            f"{container_name}-ireq-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )
    else:
        ireq_base_name = bridge_name

    use_index = check_workloads(
        pods_to_intercept,
        deployment=deployment,
        statefulset=statefulset,
        container_name=container_name,
    )

    # is is required to copy at least the service account tokens from the bridged container
    if sync_down_dirs:
        sync_down_dirs = [
            "/var/run/secrets/kubernetes.io/serviceaccount"
        ] + sync_down_dirs
    else:
        sync_down_dirs = ["/var/run/secrets/kubernetes.io/serviceaccount"]

    from gefyra.local.bridge import (
        get_ireq_body,
        handle_create_interceptrequest,
    )

    from gefyra.local.cargo import add_syncdown_job

    ireqs = []
    for idx, pod in enumerate(pods_to_intercept):
        logger.info(f"Creating bridge for Pod {pod}")
        ireq_body = get_ireq_body(
            config,
            name=f"{ireq_base_name}-{idx}" if use_index else ireq_base_name,
            destination_ip=local_container_ip,
            target_pod=pod,
            target_namespace=namespace,
            target_container=container_name,
            port_mappings=ports,
            sync_down_directories=sync_down_dirs,
            handle_probes=handle_probes,
        )
        ireq = handle_create_interceptrequest(config, ireq_body)
        logger.debug(f"Bridge {ireq['metadata']['name']} created")
        for syncdown_dir in sync_down_dirs:
            add_syncdown_job(
                config,
                ireq["metadata"]["name"],
                name,
                pod,
                container_name,
                syncdown_dir,
            )
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
    while True:
        # watch whether all relevant bridges have been established
        kube_ireqs = get_all_interceptrequests(config)
        for kube_ireq in kube_ireqs:
            if kube_ireq["metadata"]["uid"] in bridges.keys() and kube_ireq.get(
                "established", False
            ):
                bridges[str(kube_ireq["metadata"]["uid"])] = True
                logger.info(
                    f"Bridge {kube_ireq['metadata']['name']} ({sum(bridges.values())}/{len(ireqs)}) established."
                )
        if all(bridges.values()):
            break
        sleep(1)
        # Raise exception in case timeout is reached
        waiting_time -= 1
        if timeout and waiting_time <= 0:
            raise RuntimeError("Timeout for bridging operation exceeded")

    return True


@stopwatch
def unbridge(
    name: str,
    config=default_configuration,
) -> bool:
    from gefyra.local.bridge import handle_delete_interceptrequest

    success = handle_delete_interceptrequest(config, name)
    if success:
        logger.info(f"Bridge {name} removed")
    return True


@stopwatch
def unbridge_all(
    config=default_configuration,
) -> bool:
    from gefyra.local.bridge import (
        handle_delete_interceptrequest,
        get_all_interceptrequests,
    )

    ireqs = get_all_interceptrequests(config)
    for ireq in ireqs:
        name = ireq["metadata"]["name"]
        logger.info(f"Removing Bridge {name}")
        handle_delete_interceptrequest(config, name)
    return True
