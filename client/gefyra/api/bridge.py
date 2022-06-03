import logging
from datetime import datetime
from typing import List, Dict

from gefyra.configuration import default_configuration

from .utils import stopwatch

logger = logging.getLogger(__name__)


def get_pods_to_intercept(
    deployment: str, namespace: str, statefulset: str, pod: str, config
) -> Dict[str, List[str]]:
    from gefyra.cluster.resources import get_pods_and_containers_for_workload

    pods_to_intercept = {}
    if deployment:
        pods_to_intercept.update(
            get_pods_and_containers_for_workload(config, deployment, namespace)
        )
    if statefulset:
        pods_to_intercept.update(
            get_pods_and_containers_for_workload(config, statefulset, namespace)
        )
    if pod:
        pods_to_intercept.update(
            get_pods_and_containers_for_workload(config, pod, namespace)
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
    ports: List[str],
    deployment: str = None,
    statefulset: str = None,
    pod: str = None,
    container_name: str = None,
    namespace: str = "default",
    bridge_name: str = None,
    sync_down_dirs: List[str] = None,
    handle_probes: bool = True,
    config=default_configuration,
) -> bool:
    from docker.errors import NotFound

    try:
        container = config.DOCKER.containers.get(name)
    except NotFound:
        logger.error(f"Could not find target container '{name}'")
        return False

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
    from kubernetes.watch import Watch

    w = Watch()
    for event in w.stream(
        config.K8S_CORE_API.list_namespaced_event, namespace=config.NAMESPACE
    ):
        if event["object"].reason == "Established":
            for ireq in ireqs:
                if ireq["metadata"]["uid"] == event["object"].involved_object.uid:
                    logger.info(f"Bridge {ireq['metadata']['name']} established")
                    if len(ireqs) - 1 == 0:
                        return True
                    else:
                        ireqs.pop(ireq)
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
