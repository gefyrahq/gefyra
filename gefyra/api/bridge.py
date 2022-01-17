import logging

import docker

from gefyra.cluster.resources import get_pods_for_workload
from gefyra.configuration import default_configuration
from gefyra.local.bridge import deploy_app_container, get_ireq_body, handle_create_interceptrequest

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
    config=default_configuration,
) -> bool:

    container = config.DOCKER.containers.get(name)
    local_container_ip = container.attrs["NetworkSettings"]["Networks"][config.NETWORK_NAME]["IPAddress"]

    pods_to_intercept = []
    if deployment:
        pods_to_intercept.extend(get_pods_for_workload(config, deployment, namespace))
    if statefulset:
        pods_to_intercept.extend(get_pods_for_workload(config, deployment, namespace))
    if pod:
        pods_to_intercept.extend(pod)
    pass

    for pod in pods_to_intercept:
        logger.info(f"Creating intercept request for Pod {pod}")
        ireq_body = get_ireq_body(
            config,
            destination_ip=local_container_ip,
            destination_port=port,
            target_pod=pod,
            target_namespace=namespace,
            target_container=container_name,
            target_container_port=container_port,
        )
        ireq = handle_create_interceptrequest(config, ireq_body)
        logger.info(f"Interceptrequest {ireq} created")
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
        container = deploy_app_container(config, image, name, command, volumes, ports, auto_remove, dns_search)
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
