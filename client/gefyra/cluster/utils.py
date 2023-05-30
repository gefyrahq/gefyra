import base64
import logging
from collections.abc import Mapping
from time import sleep

from gefyra.configuration import ClientConfiguration


logger = logging.getLogger(__name__)


def decode_secret(u):
    n = {}
    for k, v in u.items():
        if isinstance(v, Mapping):
            n[k] = decode_secret(v)
        else:
            n[k] = (base64.b64decode(v.encode("utf-8"))).decode("utf-8")
    return n


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
                sleep(interval)
                counter += 1
                logger.debug(
                    f"Failed to get env from pod {pod_name} in namespace {namespace} on try {counter}."
                )
            else:
                raise e
    raise RuntimeError(
        f"Failed to get env from pod {pod_name} in namespace {namespace} after {retries} tries."
    )


def get_container(pod, container_name: str):
    for container in pod.spec.containers:
        if container.name == container_name:
            return container
    raise RuntimeError(f"Container {container_name} not found.")


def get_container_image(pod, container_name: str):
    container = get_container(pod, container_name=container_name)
    if container.image:
        return container.image
    raise RuntimeError(f"Container {container_name} image could not be determined.")


def get_container_command(pod, container_name: str):
    container = get_container(pod, container_name=container_name)
    res = []
    if container.command:
        res.extend(container.command)
    if container.args:
        res.extend(container.args)
    return " ".join(res)


def get_container_ports(pod, container_name: str):
    container = get_container(pod, container_name=container_name)
    if container.ports:
        return container.ports
    return []


def get_v1pod(
    config: ClientConfiguration,
    pod_name: str,
    namespace: str,
):
    from kubernetes.client import ApiException

    try:
        pod = config.K8S_CORE_API.read_namespaced_pod(pod_name, namespace)
    except ApiException as e:
        if e.status == 404:
            raise RuntimeError(
                f"Pod {pod_name} in namespace {namespace} does not exist."
            )
        else:
            raise e
    return pod
