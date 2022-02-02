import base64
import collections
import logging

import kubernetes as k8s

from gefyra.configuration import ClientConfiguration


logger = logging.getLogger(__name__)


def decode_secret(u):
    n = {}
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            n[k] = decode_secret(v)
        else:
            n[k] = (base64.b64decode(v.encode("utf-8"))).decode("utf-8")
    return n


def get_env_from_pod_container(
    config: ClientConfiguration, pod_name: str, namespace: str, container_name: str
):
    resp = k8s.stream.stream(
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
