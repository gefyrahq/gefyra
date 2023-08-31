import logging
from typing import List, Dict, Union
from gefyra.exceptions import PodNotFoundError, WorkloadNotFoundError

from kubernetes.client import (
    V1Deployment,
    V1Container,
    ApiException,
    V1StatefulSet,
    V1Pod,
)

from gefyra.api.utils import get_workload_type
from gefyra.configuration import ClientConfiguration

logger = logging.getLogger(__name__)


def _check_pod_for_command(pod: V1Pod, container_name: str):
    containers: list[V1Container] = pod.spec.containers
    if not len(containers):
        raise RuntimeError(f"No container available in pod {pod.metadata.name}.")

    ALLOWED_COMMANDS = [
        "sh",
        "bash",
        "zsh",
        "ash",
        "/bin/sh",
        "/bin/bash",
        "/bin/zsh",
        "/bin/ash",
        "/entrypoint.sh",
    ]
    for container in containers:
        if (
            container.name == container_name
            and container.command
            and container.command[0] not in ALLOWED_COMMANDS
        ):
            raise RuntimeError(
                f"Cannot bridge pod {pod.metadata.name} since it has a `command`"
                " defined."
            )


def check_pod_valid_for_bridge(
    config: ClientConfiguration, pod_name: str, namespace: str, container_name: str
):
    pod = config.K8S_CORE_API.read_namespaced_pod(
        name=pod_name,
        namespace=namespace,
    )

    _check_pod_for_command(pod, container_name)


def owner_reference_consistent(
    pod: V1Pod,
    workload: Union[V1Deployment, V1StatefulSet],
    config: ClientConfiguration,
) -> bool:
    if workload.kind == "StatefulSet":
        return pod.metadata.owner_references[0].uid == workload.metadata.uid
    elif workload.kind == "Deployment":
        try:
            replicaset_set = config.K8S_APP_API.read_namespaced_replica_set(
                name=pod.metadata.owner_references[0].name,
                namespace=pod.metadata.namespace,
            )
        except ApiException as e:
            if e.status == 404:
                return False
        return replicaset_set.metadata.owner_references[0].uid == workload.metadata.uid
    raise RuntimeError(
        "Unknown workload type for owner reference check:"
        f" {workload.kind}/{workload.metadata.name}."
    )


def get_pods_and_containers_for_workload(
    config: ClientConfiguration, name: str, namespace: str, workload_type: str
) -> Dict[str, List[str]]:
    result = {}
    API_EXCEPTION_MSG = "Exception when calling Kubernetes API: {}"
    workload_type = get_workload_type(workload_type)
    NOT_FOUND_MSG = f"{workload_type.capitalize()} not found."
    try:
        if workload_type == "deployment":
            workload = config.K8S_APP_API.read_namespaced_deployment(
                name=name, namespace=namespace
            )
        elif workload_type == "statefulset":
            workload = config.K8S_APP_API.read_namespaced_stateful_set(
                name=name, namespace=namespace
            )
    except ApiException as e:
        if e.status == 404:
            raise WorkloadNotFoundError(NOT_FOUND_MSG)
        raise RuntimeError(API_EXCEPTION_MSG.format(e))

    # use workloads metadata uuid for owner references with field selector to get pods
    v1_label_selector = workload.spec.selector.match_labels

    label_selector = ",".join(
        [f"{key}={value}" for key, value in v1_label_selector.items()]
    )

    if not label_selector:
        raise WorkloadNotFoundError(
            f"No label selector set for {workload_type} - {name}."
        )

    pods = config.K8S_CORE_API.list_namespaced_pod(
        namespace=namespace, label_selector=label_selector
    )
    for pod in pods.items:
        if owner_reference_consistent(pod, workload, config):
            result[pod.metadata.name] = [
                container.name for container in pod.spec.containers
            ]
    return result


def get_pods_and_containers_for_pod_name(
    config: ClientConfiguration, name: str, namespace: str
) -> Dict[str, List[str]]:
    result = {}
    API_EXCEPTION_MSG = "Exception when calling Kubernetes API: {}"
    try:
        pod = config.K8S_CORE_API.read_namespaced_pod(name=name, namespace=namespace)
    except ApiException as e:
        if e.status == 404:
            API_EXCEPTION_MSG = f"Pod {name} not found."
        raise PodNotFoundError(API_EXCEPTION_MSG.format(e))
    if not pod.spec:  # `.spec` is optional in python kubernetes client
        raise PodNotFoundError(f"Could not retrieve spec for pod - {name}.")
    result[pod.metadata.name] = [container.name for container in pod.spec.containers]
    return result
