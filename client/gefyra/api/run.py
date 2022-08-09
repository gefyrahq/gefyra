import logging
import os

from gefyra.configuration import default_configuration, ClientConfiguration
from .utils import stopwatch


logger = logging.getLogger(__name__)


def get_workload_type(workload_type_str: str):
    POD = ["pod", "po", "pods"]
    DEPLOYMENT = ["deploy", "deployment", "deployments"]
    STATEFULSET = ["statefulset", "sts", "statefulsets"]
    VALID_TYPES = POD + DEPLOYMENT + STATEFULSET

    if workload_type_str not in VALID_TYPES:
        raise RuntimeError(f"Unknown workload type {workload_type_str}")

    if workload_type_str in POD:
        return "pod"
    elif workload_type_str in DEPLOYMENT:
        return "deployment"
    elif workload_type_str in STATEFULSET:
        return "statefulset"


def retrieve_pod_and_container(
    env_from: str, namespace: str, config: ClientConfiguration
) -> (str, str):
    from gefyra.cluster.resources import (
        get_pods_and_containers_for_workload,
        get_pods_and_containers_for_pod_name,
    )

    container_name = ""
    workload_type, workload_name = env_from.split("/", 1)

    workload_type = get_workload_type(workload_type)

    if "/" in workload_name:
        workload_name, container_name = workload_name.split("/")

    if workload_type != "pod":
        pods = get_pods_and_containers_for_workload(
            config, name=workload_name, namespace=namespace, workload_type=workload_type
        )
    else:
        pods = get_pods_and_containers_for_pod_name(
            config=config, name=workload_name, namespace=namespace
        )
    pod_name, containers = pods.popitem()

    if container_name and container_name not in containers:
        raise RuntimeError(
            f"{container_name} was not found for {workload_type}/{workload_name}"
        )

    return pod_name, container_name or containers[0]


@stopwatch
def run(
    image: str,
    name: str = None,
    command: str = None,
    volumes: dict = None,
    ports: dict = None,
    detach: bool = True,
    auto_remove: bool = True,
    namespace: str = None,
    env: list = None,
    env_from: str = None,
    config=default_configuration,
) -> bool:
    from kubernetes.client import ApiException
    from gefyra.cluster.utils import get_env_from_pod_container
    from gefyra.local.bridge import deploy_app_container
    from gefyra.local.utils import get_processed_paths, set_gefyra_network_from_cargo
    from gefyra.local.cargo import probe_wireguard_connection
    from docker.errors import APIError

    # #125: Fallback to namespace in kube config
    if namespace is None:
        from kubernetes.config import kube_config

        _, active_context = kube_config.list_kube_config_contexts()
        namespace = active_context["context"].get("namespace") or "default"
        ns_source = "kubeconfig"
    else:
        ns_source = "--namespace argument"

    dns_search = f"{namespace}.svc.cluster.local"
    config = set_gefyra_network_from_cargo(config)
    #
    # Confirm the wireguard connection working
    #
    try:
        probe_wireguard_connection(config)
    except Exception as e:
        logger.error(e)
        return False

    volumes = get_processed_paths(os.getcwd(), volumes)
    #
    # 1. get the ENV together a) from a K8s container b) from override
    #
    env_dict = {}
    try:
        if env_from:

            env_from_pod, env_from_container = retrieve_pod_and_container(
                env_from, namespace=namespace, config=config
            )

            raw_env = get_env_from_pod_container(
                config, env_from_pod, namespace, env_from_container
            )
            logger.debug("ENV from pod/container is:\n" + raw_env)
            env_dict = {
                k[0]: k[1]
                for k in [arg.split("=") for arg in raw_env.split("\n")]
                if len(k) > 1
            }
    except ApiException as e:
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
    except APIError as e:
        if e.status_code == 409:
            logger.warning("This container is already deployed and running")
            return True
        else:
            logger.error(e)
            return False

    logger.info(
        f"Container image '{', '.join(container.image.tags)}' started with name '{container.name}' in "
        f"Kubernetes namespace '{namespace}' (from {ns_source})"
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
