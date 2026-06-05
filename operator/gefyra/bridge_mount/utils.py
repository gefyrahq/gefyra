import asyncio
import base64
from functools import partial
import time
from typing import List
import kubernetes as k8s
from kubernetes.client import (
    V1Deployment,
    V1StatefulSet,
    V1Pod,
    V1ServicePort,
    V1Service,
    V1Container,
    V1Probe,
)

from gefyra.bridge.carrier2.config import CarrierTLS
from gefyra.utils import wait_until_condition

from gefyra.bridge.carrier2.utils import read_carrier2_file, stream_exec_retries

core_v1_api = k8s.client.CoreV1Api()

INJECTED_TLS_KEY = "/tmp/from_k8s_secret_key_{port}.pem"
INJECTED_TLS_CERT = "/tmp/from_k8s_secret_cert_{port}.pem"

_K8S_SECRET_CACHE = {}  # (namespace, name) -> (data, timestamp)


def get_upstreams_for_svc(svc: V1Service, rport: int | None = None) -> list[str]:
    res = []
    name = svc.metadata.name
    namespace = svc.metadata.namespace
    for port in svc.spec.ports:
        if not rport or (rport and port.port == rport):
            res.append(f"{name}.{namespace}.svc.cluster.local:{port.port}")
    return res


def generate_k8s_conform_name(name: str, suffix: str, max_length: int = 63) -> str:
    """
    Generate a k8s conform name with a suffix.
    """
    if len(name) + len(suffix) <= max_length:
        return f"{name}{suffix}"
    return name[: max_length - len(suffix)] + suffix


def generate_duplicate_svc_name(workload_name: str, container_name: str) -> str:
    base = f"{workload_name}-{container_name}"
    suffix = "-gefyra-svc"

    return generate_k8s_conform_name(base, suffix)


def generate_duplicate_workload_name(workload_name: str):
    suffix = "-gefyra"
    return generate_k8s_conform_name(workload_name, suffix)


def get_duplicate_svc_fqdn(
    workload_name: str, container_name: str, namespace: str
) -> str:
    return f"{generate_duplicate_svc_name(workload_name, container_name)}.{namespace}.svc.cluster.local"


def get_ports_for_workload(
    workload: V1Deployment | V1StatefulSet | V1Pod, container_name: str
) -> list[V1ServicePort]:
    ports = []
    if hasattr(workload.spec, "template") and workload.spec.template is not None:
        spec_ = workload.spec.template.spec
    else:
        spec_ = workload.spec
    for container in spec_.containers:
        if container.name == container_name:
            for idx, port in enumerate(container.ports):
                ports.append(
                    V1ServicePort(
                        name=f"{port.container_port}-{idx}",
                        port=port.container_port,
                        target_port=port.container_port,
                    )
                )
    return ports


def _read_k8s_secret_tls_value(name: str, key: str, namespace: str = "default") -> str:
    """
    Reads a Kubernetes secret and caches its content for a minute.
    Extracts the value of the specified key and returns it base64 decoded.
    """
    now = time.time()
    cache_key = (namespace, name)

    if cache_key in _K8S_SECRET_CACHE:
        data, timestamp = _K8S_SECRET_CACHE[cache_key]
        if now - timestamp < 60:
            if key in data:
                try:
                    return base64.b64decode(data[key]).decode("utf-8")
                except Exception as e:
                    raise Exception(
                        f"Could not base64 decode key '{key}' in secret '{name}' "
                        f"from namespace '{namespace}': {e}"
                    )

    try:
        secret = core_v1_api.read_namespaced_secret(name, namespace)
        if not secret.data:
            raise Exception(f"Secret '{name}' in namespace '{namespace}' has no data")

        _K8S_SECRET_CACHE[cache_key] = (secret.data, now)

        if key not in secret.data:
            raise Exception(
                f"Key '{key}' not found in secret '{name}' in namespace '{namespace}'"
            )

        try:
            return base64.b64decode(secret.data[key]).decode("utf-8")
        except Exception as e:
            raise Exception(
                f"Could not base64 decode key '{key}' in secret '{name}' "
                f"from namespace '{namespace}': {e}"
            )
    except k8s.client.ApiException as e:
        raise Exception(
            f"Failed to read secret '{name}' in namespace '{namespace}' "
            f"from Kubernetes API: {e.reason} ({e.status})"
        )


def _tls_param_from_key_secret(
    which: str, params: dict, rport: int | None = None
) -> bool:
    if rport and str(rport) in params and "tls" in params[str(rport)]:
        _port = str(rport)
        _tls_param = params[_port]["tls"][which]
    elif "tls" in params:
        _tls_param = params["tls"][which]
    else:
        return False

    if isinstance(_tls_param, dict) and "secret" in _tls_param:
        return True
    return False


def _tls_cert_from_k8s_secret(params: dict, rport: int | None = None) -> bool:
    return _tls_param_from_key_secret("certificate", params, rport)


def _tls_key_from_k8s_secret(params: dict, rport: int | None = None) -> bool:
    return _tls_param_from_key_secret("key", params, rport)


async def update_tls_file(
    logger,
    pod_name: str,
    container: str,
    namespace: str,
    which: str,
    params: dict,
    rport: int | None = None,
) -> bool:
    try:
        if rport and str(rport) in params and "tls" in params[str(rport)]:
            _port = str(rport)
            _tls_param = params[_port]["tls"][which]
        elif "tls" in params:
            _port = "all"
            _tls_param = params["tls"][which]
    except KeyError:
        raise ValueError(
            "Only 'certificate' or 'key' are supported values for the 'which' parameter."
        )

    if which == "certificate":
        file_name = INJECTED_TLS_CERT.format(port=_port)
    else:
        file_name = INJECTED_TLS_KEY.format(port=_port)

    content_from_secret = _read_k8s_secret_tls_value(
        _tls_param["secret"]["name"],
        _tls_param["secret"]["key"],
        _tls_param["secret"]["namespace"],
    )
    content_from_container = await asyncio.to_thread(
        read_carrier2_file, logger, pod_name, namespace, file_name, container
    )
    if content_from_secret.strip() != content_from_container[0].strip():
        logger.info(f"Update to TLS {which} from Kubernetes secret detected")
        await inject_tls_file(
            logger,
            pod_name,
            container.name,
            namespace,
            which,
            params,
            rport,
        )
        return True
    return False


async def inject_tls_file(
    logger,
    pod_name: str,
    container: str,
    namespace: str,
    which: str,
    params: dict,
    rport: int | None = None,
):
    try:
        if rport and str(rport) in params and "tls" in params[str(rport)]:
            _port = str(rport)
            _tls_param = params[_port]["tls"][which]
        elif "tls" in params:
            _port = "all"
            _tls_param = params["tls"][which]
    except KeyError:
        raise ValueError(
            "Only 'certificate' or 'key' are supported values for the 'which' parameter."
        )

    if which == "certificate":
        file_name = INJECTED_TLS_CERT.format(port=_port)
    else:
        file_name = INJECTED_TLS_KEY.format(port=_port)

    logger.info(f"Injecting TLS file from Kubernetes secret: {file_name}")
    content = _read_k8s_secret_tls_value(
        _tls_param["secret"]["name"],
        _tls_param["secret"]["key"],
        _tls_param["secret"]["namespace"],
    )

    core_v1 = k8s.client.CoreV1Api()
    read_func = partial(core_v1.read_namespaced_pod_status, pod_name, namespace)

    # busy wait for pod to get ready, raises RuntimeError on timeout
    await asyncio.to_thread(
        wait_until_condition,
        read_func,
        lambda s: all(
            [
                bool(
                    container.state
                    and container.state.running
                    and container.state.running.started_at
                )
                for container in s.status.container_statuses
            ]
        ),
        timeout=120,
        backoff=2,
    )

    write_command = [
        f"cat <<'EOF' > {file_name}\n{content}",
        "EOF",
    ]
    stream_exec_retries(logger, pod_name, namespace, container, write_command)


def _get_tls_from_provider_parameters(
    params: dict, rport: int | None = None
) -> CarrierTLS | None:
    if rport and str(rport) in params and "tls" in params[str(rport)]:
        _port = str(rport)
        _cert_param = params[_port]["tls"]["certificate"]
        _key_param = params[_port]["tls"]["key"]

        if "sni" in params[_port]["tls"]:
            _sni_param = params[_port]["tls"]["sni"]
        else:
            _sni_param = None
    elif "tls" in params:
        _port = "all"
        _cert_param = params["tls"]["certificate"]
        _key_param = params["tls"]["key"]

        if "sni" in params["tls"]:
            _sni_param = params["tls"]["sni"]
        else:
            _sni_param = None

    else:
        # if none of the above tls settings are set
        return None

    if isinstance(_cert_param, dict) and "secret" in _cert_param:
        cert = INJECTED_TLS_CERT.format(port=_port)
    else:
        cert = _cert_param
    if isinstance(_key_param, dict) and "secret" in _key_param:
        key = INJECTED_TLS_KEY.format(port=_port)
    else:
        key = _key_param
    if isinstance(_sni_param, dict) and "secret" in _sni_param:
        sni = _read_k8s_secret_tls_value(
            _sni_param["name"], _sni_param["key"], _sni_param["namespace"]
        )
    else:
        sni = _sni_param

    return CarrierTLS(
        certificate=cert,
        key=key,
        sni=sni,
    )


def get_all_probes(container: V1Container) -> List[V1Probe]:
    probes = []
    if container.startup_probe:
        probes.append(container.startup_probe)
    if container.readiness_probe:
        probes.append(container.readiness_probe)
    if container.liveness_probe:
        probes.append(container.liveness_probe)
    return probes
