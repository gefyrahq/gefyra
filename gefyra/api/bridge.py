import logging
from datetime import datetime

import docker

from gefyra.cluster.resources import get_pods_for_workload
from gefyra.configuration import default_configuration
from gefyra.local.bridge import (
    deploy_app_container,
    get_ireq_body,
    handle_create_interceptrequest,
    handle_delete_interceptrequest,
    get_all_interceptrequests,
)

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
        )
        ireq = handle_create_interceptrequest(config, ireq_body)
        logger.info(f"Bridge {ireq['metadata']['name']} created")
    return True


@stopwatch
def run(
    image: str,
    name: str = None,
    command: str = None,
    volumes: dict = None,
    ports: dict = None,
    detach: bool = True,
    auto_remove: bool = True,
    namespace: str = "default",
    config=default_configuration,
) -> bool:
    dns_search = f"{namespace}.svc.cluster.local"
    try:
        container = deploy_app_container(
            config, image, name, command, volumes, ports, auto_remove, dns_search
        )
    except docker.errors.APIError as e:
        if e.status_code == 409:
            logger.warning("This container is already deployed and running")
            return True
        else:
            logger.error(e)
            return False

    logger.info(
        f"Container image '{', '.join(container.image.tags)}' started with name '{container.name}' in "
        f"Kubernetes namespace '{namespace}'"
    )
    if detach:
        return True
    else:
        logger.debug("Now printing out logs")
        for logline in container.logs(stream=True):
            print(logline)


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
