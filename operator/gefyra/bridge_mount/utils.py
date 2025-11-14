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

core_v1_api = k8s.client.CoreV1Api()


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
    if isinstance(workload, (V1Deployment, V1StatefulSet)):
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


def _get_tls_from_provider_parameters(
    params: dict, rport: int | None = None
) -> CarrierTLS | None:
    if rport and str(rport) in params and "tls" in params[str(rport)]:
        return CarrierTLS(
            certificate=params[str(rport)]["tls"]["certificate"],
            key=params[str(rport)]["tls"]["key"],
            sni=params[str(rport)]["tls"].get("sni", None),
        )
    elif "tls" in params:
        return CarrierTLS(
            certificate=params["tls"]["certificate"],
            key=params["tls"]["key"],
            sni=params["tls"].get("sni", None),
        )
    else:
        return None


def get_all_probes(container: V1Container) -> List[V1Probe]:
    probes = []
    if container.startup_probe:
        probes.append(container.startup_probe)
    if container.readiness_probe:
        probes.append(container.readiness_probe)
    if container.liveness_probe:
        probes.append(container.liveness_probe)
    return probes
