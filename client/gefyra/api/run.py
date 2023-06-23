from docker.models.containers import Container
import logging
import os
import sys
from threading import Thread, Event
from typing import Dict, List, Optional, Tuple

from gefyra.configuration import (
    ClientConfiguration,
)
from .utils import generate_env_dict_from_strings, stopwatch, get_workload_type


logger = logging.getLogger(__name__)

stop_thread = Event()


def pod_ready_and_healthy(
    config: ClientConfiguration, pod_name: str, namespace: str, container_name: str
):
    pod = config.K8S_CORE_API.read_namespaced_pod_status(pod_name, namespace=namespace)

    container_idx = next(
        i
        for i, container_status in enumerate(pod.status.container_statuses)
        if container_status.name == container_name
    )

    return (
        pod.status.phase == "Running"
        and pod.status.container_statuses[container_idx].ready
        and pod.status.container_statuses[container_idx].started
        and pod.status.container_statuses[container_idx].state.running
        and pod.status.container_statuses[container_idx].state.running.started_at
    )


def retrieve_pod_and_container(
    env_from: str, namespace: str, config: ClientConfiguration
) -> Tuple[str, str]:
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

    while len(pods):
        pod_name, containers = pods.popitem()
        if container_name and container_name not in containers:
            raise RuntimeError(
                f"{container_name} was not found for {workload_type}/{workload_name}"
            )
        actual_container_name = container_name or containers[0]
        if pod_ready_and_healthy(config, pod_name, namespace, actual_container_name):
            return pod_name, actual_container_name

    raise RuntimeError(
        f"Could not find a ready pod for {workload_type}/{workload_name}"
    )


def print_logs(container: Container):
    for logline in container.logs(stream=True):
        print(logline.decode("utf-8"), end="")


def check_input():
    line = sys.stdin.readline()
    if not line:
        stop_thread.set()


@stopwatch
def run(
    image: str,
    connection_name: str,
    name: str = "",
    command: str = "",
    volumes: Optional[List] = None,
    ports: Optional[Dict] = None,
    detach: bool = True,
    auto_remove: bool = False,
    namespace: str = "",
    env: Optional[List] = None,
    env_from: str = "",
) -> bool:
    from kubernetes.client import ApiException
    from docker.errors import APIError
    from gefyra.cluster.utils import get_env_from_pod_container
    from gefyra.local.bridge import deploy_app_container
    from gefyra.local.utils import (
        get_processed_paths,
    )
    from gefyra.local.cargo import probe_wireguard_connection

    config = ClientConfiguration(connection_name=connection_name)

    # #125: Fallback to namespace in kube config
    if not namespace:
        from kubernetes.config import kube_config

        _, active_context = kube_config.list_kube_config_contexts()
        namespace = active_context["context"].get("namespace") or "default"
        ns_source = "kubeconfig"
    else:
        ns_source = "--namespace argument"

    dns_search = f"{namespace}.svc.cluster.local"
    #
    # Confirm the wireguard connection working
    #
    try:
        probe_wireguard_connection(config)
    except Exception as e:
        logger.error(e)
        return False

    if volumes:
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
            logger.debug(f"Using ENV from {env_from_pod}/{env_from_container}")
            raw_env = get_env_from_pod_container(
                config, env_from_pod, namespace, env_from_container
            )
            logger.debug("ENV from pod/container is:\n" + raw_env)
            raw_env_vars = raw_env.split("\n")
            env_dict = generate_env_dict_from_strings(raw_env_vars)
    except ApiException as e:
        raise e
        logger.error(f"Cannot copy environment from Pod: {e.reason} ({e.status}).")
        return False
    if env:
        env_overrides = generate_env_dict_from_strings(env)
        env_dict.update(env_overrides)

    #
    # 2. deploy the requested container to Gefyra
    #
    try:
        container = deploy_app_container(
            config=config,
            image=image,
            name=name,
            command=command,
            ports=ports,
            env=env_dict,
            dns_search=dns_search,
            auto_remove=auto_remove,
            volumes=volumes,
        )
    except APIError as e:
        if e.status_code == 409:
            logger.warning(e.explanation)
            return True
        else:
            raise RuntimeError(e.explanation)

    logger.info(
        f"Container image '{', '.join(container.image.tags)}' started with name"
        f" '{container.name}' in Kubernetes namespace '{namespace}' (from {ns_source})"
    )
    if detach:
        return True
    else:
        try:
            logger.debug("Now printing out logs")
            t = Thread(target=print_logs, args=[container], daemon=True)
            t.start()
            input_thread = Thread(target=check_input, daemon=True)
            input_thread.start()
            while t.is_alive():
                if stop_thread.is_set():
                    logger.info(f"Detached from container: {name}")
                    return True
        except KeyboardInterrupt:
            container.stop()
            logger.info(f"Container stopped: {name}")
    return True
