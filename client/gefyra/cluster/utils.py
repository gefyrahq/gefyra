import logging
from time import sleep
from typing import Tuple

from gefyra.configuration import ClientConfiguration


logger = logging.getLogger(__name__)


def get_env_from_pod_container(
    config: ClientConfiguration, pod_name: str, namespace: str, container_name: str
):
    from kubernetes.client import ApiException
    from kubernetes.stream import stream

    retries = 10
    counter = 0
    interval = 1
    while counter < retries:
        try:
            resp = stream(
                config.K8S_CORE_API.connect_get_namespaced_pod_exec,
                pod_name,
                namespace,
                container=container_name,
                command=["env"],
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
            )
            return resp
        except ApiException as e:
            # e.status is 0 for some reason
            if "500 Internal Server Error" in e.reason:
                # this could be a faulty K8s call, or Carrier/2 is running already
                try:
                    resp = stream(
                        config.K8S_CORE_API.connect_get_namespaced_pod_exec,
                        pod_name,
                        namespace,
                        container=container_name,
                        command=["busybox", "env"],
                        stderr=True,
                        stdin=False,
                        stdout=True,
                        tty=False,
                    )
                    return resp
                except ApiException:
                    pass

                sleep(interval)
                counter += 1
                logger.debug(
                    f"Failed to get env from pod {pod_name} in namespace {namespace} on"
                    f" try {counter}."
                )
            else:
                raise e
    raise RuntimeError(
        f"Failed to get env from pod {pod_name} in namespace {namespace} after"
        f" {retries} tries."
    )


def is_operator_running(config: ClientConfiguration) -> bool:
    from kubernetes.client import ApiException

    try:
        deploy = config.K8S_APP_API.read_namespaced_deployment(
            name="gefyra-operator", namespace=config.NAMESPACE
        )
        return deploy.status.ready_replicas == 1
    except ApiException:
        return False


def retrieve_pod_and_container(
    workload: str, namespace: str, config: ClientConfiguration
) -> Tuple[str, str]:
    from gefyra.cluster.resources import (
        get_pods_and_containers_for_workload,
        get_pods_and_containers_for_pod_name,
    )
    from gefyra.api.utils import get_workload_type

    container_name = ""
    workload_type, workload_name = workload.split("/", 1)

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
