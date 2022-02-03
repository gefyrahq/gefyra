import logging
from datetime import datetime
from typing import List

import kubernetes
from gefyra.cluster.resources import get_pods_for_workload
from gefyra.configuration import default_configuration
from gefyra.local.bridge import (
    get_ireq_body,
    handle_create_interceptrequest,
    handle_delete_interceptrequest,
    get_all_interceptrequests,
)
from gefyra.local.cargo import add_syncdown_job

from .utils import stopwatch

logger = logging.getLogger(__name__)


@stopwatch
def bridge(
    name: str,
    port: int,
    deployment: str = None,
    statefulset: str = None,
    pod: str = None,
    container_name: str = None,
    container_port: str = None,
    namespace: str = "default",
    bridge_name: str = None,
    sync_down_dirs: List[str] = None,
    config=default_configuration,
) -> bool:
    container = config.DOCKER.containers.get(name)
    local_container_ip = container.attrs["NetworkSettings"]["Networks"][
        config.NETWORK_NAME
    ]["IPAddress"]

    pods_to_intercept = []
    if deployment:
        pods_to_intercept.extend(get_pods_for_workload(config, deployment, namespace))
    if statefulset:
        pods_to_intercept.extend(get_pods_for_workload(config, statefulset, namespace))
    if pod:
        pods_to_intercept.extend(pod)
    pass

    if not bridge_name:
        ireq_base_name = (
            f"{container_name}-ireq-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )
    else:
        ireq_base_name = bridge_name
    if len(pods_to_intercept) > 1:
        use_index = True
    else:
        use_index = False

    # is is required to copy at least the service account tokens from the bridged container
    if sync_down_dirs:
        sync_down_dirs = [
            "/var/run/secrets/kubernetes.io/serviceaccount"
        ] + sync_down_dirs
    else:
        sync_down_dirs = ["/var/run/secrets/kubernetes.io/serviceaccount"]

    ireqs = []
    for idx, pod in enumerate(pods_to_intercept):
        logger.info(f"Creating bridge for Pod {pod}")
        ireq_body = get_ireq_body(
            config,
            name=f"{ireq_base_name}-{idx}" if use_index else ireq_base_name,
            destination_ip=local_container_ip,
            destination_port=port,
            target_pod=pod,
            target_namespace=namespace,
            target_container=container_name,
            target_container_port=container_port,
            sync_down_directories=sync_down_dirs,
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
    w = kubernetes.watch.Watch()
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
    success = handle_delete_interceptrequest(config, name)
    if success:
        logger.info(f"Bridge {name} removed")
    return True


@stopwatch
def unbridge_all(
    config=default_configuration,
) -> bool:
    ireqs = get_all_interceptrequests(config)
    for ireq in ireqs:
        name = ireq["metadata"]["name"]
        logger.info(f"Removing Bridge {name}")
        handle_delete_interceptrequest(config, name)
    return True
