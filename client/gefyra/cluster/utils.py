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
