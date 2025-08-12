import logging
import os
import sys
from threading import Thread, Event
from typing import Dict, List, Optional, TYPE_CHECKING
from gefyra.cluster.utils import retrieve_pod_and_container

from ..cli.utils import _inherit_resources_from_workload, _parse_k8s_cpu_to_cpus, _parse_k8s_mem_to_bytes

if TYPE_CHECKING:
    from docker.models.containers import Container

from gefyra.configuration import (
    ClientConfiguration,
)
from .utils import generate_env_dict_from_strings, stopwatch


logger = logging.getLogger(__name__)

stop_thread = Event()


def print_logs(container: "Container"):
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
    pull: str = "missing",
    platform: str = "linux/amd64",
    cpu_from: Optional[str] = None,
    memory_from: Optional[str] = None,
    cpu: Optional[str] = None,
    memory: Optional[str] = None,

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

    dns_search = (
        f"{namespace}.svc.cluster.local svc.cluster.local cluster.local k8s".split(" ")
    )
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
        logger.error(f"Cannot copy environment from Pod: {e.reason} ({e.status}).")
        return False
    if env:
        env_overrides = generate_env_dict_from_strings(env)
        env_dict.update(env_overrides)

    # Inherit CPU/memory from workloads if requested
    inherited_cpu: Optional[str] = None
    inherited_mem: Optional[str] = None
    if cpu_from:
        inherited_cpu, _ = _inherit_resources_from_workload(config, namespace, cpu_from)
    if memory_from:
        _, inherited_mem = _inherit_resources_from_workload(
            config, namespace, memory_from
        )

    # Choose final CPU/memory (explicit wins)
    final_cpu_qty = cpu if cpu is not None else inherited_cpu
    final_mem_qty = memory if memory is not None else inherited_mem

    # Map to Docker-native
    cpus = _parse_k8s_cpu_to_cpus(final_cpu_qty) if final_cpu_qty else None
    mem_limit = _parse_k8s_mem_to_bytes(final_mem_qty) if final_mem_qty else None

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
            pull=pull,
            platform=platform,
            cpus=cpus,
            mem_limit=mem_limit,

        )
    except APIError as e:
        if e.status_code == 409:
            logger.error(e.explanation)
            logger.error(
                f"\n\033[1m[Hint]\033[0m You could remove the container via: \ndocker rm {name}"
            )
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
