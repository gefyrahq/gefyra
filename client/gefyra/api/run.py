import logging

import docker
import kubernetes

from gefyra.cluster.utils import get_env_from_pod_container
from gefyra.configuration import default_configuration
from gefyra.local.bridge import deploy_app_container

from .utils import stopwatch

logger = logging.getLogger(__name__)


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
    env: list = None,
    env_from: str = None,
    config=default_configuration,
) -> bool:
    dns_search = f"{namespace}.svc.cluster.local"

    #
    # 1. get the ENV together a) from a K8s container b) from override
    #
    env_dict = {}
    try:
        if env_from:
            env_from_pod, env_from_container = env_from.split("/")
            raw_env = get_env_from_pod_container(
                config, env_from_pod, namespace, env_from_container
            )
            logger.debug("ENV from pod/container is:\n" + raw_env)
            env_dict = {
                k[0]: k[1]
                for k in [arg.split("=") for arg in raw_env.split("\n")]
                if len(k) > 1
            }
    except kubernetes.client.exceptions.ApiException as e:
        logger.error(f"Cannot copy environment from Pod: {e.reason}")
        return False
    if env:
        env_overrides = {
            k[0]: k[1] for k in [arg.split("=") for arg in env] if len(k) > 1
        }
        env_dict.update(env_overrides)

    #
    # 2. deploy the requested container to Gefyra
    #
    try:
        container = deploy_app_container(
            config,
            image,
            name,
            command,
            volumes,
            ports,
            env_dict,
            auto_remove,
            dns_search,
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
        #
        # 3. print out logs if not detached
        #
        logger.debug("Now printing out logs")
        for logline in container.logs(stream=True):
            print(logline)
