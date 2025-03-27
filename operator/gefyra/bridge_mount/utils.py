from typing import List
import kubernetes as k8s
from kubernetes.client import (
    V1Deployment,
    V1ServicePort,
    V1Service,
    V1Container,
    V1Probe,
)

core_v1_api = k8s.client.CoreV1Api()


def get_upstreams_for_svc(svc: V1Service, namespace: str) -> list[str]:
    res = []
    name = svc.metadata.name
    namespace = svc.metadata.namespace
    for port in svc.spec.ports:
        res.append(f"{name}.{namespace}.svc.cluster.local:{port.port}")
    return res


def generate_duplicate_svc_name(workload_name: str, container_name: str) -> str:
    # TODO must not be longer than 63 chars
    return f"{workload_name}-{container_name}-gefyra-svc"


def get_duplicate_svc_fqdn(
    workload_name: str, container_name: str, namespace: str
) -> str:
    return f"{generate_duplicate_svc_name(workload_name, container_name)}.{namespace}.svc.cluster.local"


def get_ports_for_deployment(
    deployment: V1Deployment, container_name: str
) -> list[V1ServicePort]:
    ports = []
    for container in deployment.spec.template.spec.containers:
        if container.name == container_name:
            for port in container.ports:
                ports.append(
                    V1ServicePort(
                        port=port.container_port,
                        target_port=port.container_port,
                    )
                )
    return ports


def get_all_probes(container: V1Container) -> List[V1Probe]:
    probes = []
    if container.startup_probe:
        probes.append(container.startup_probe)
    if container.readiness_probe:
        probes.append(container.readiness_probe)
    if container.liveness_probe:
        probes.append(container.liveness_probe)
    return probes
