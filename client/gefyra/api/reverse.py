from datetime import datetime
import random
import string
from time import sleep
from typing import Dict, List, Optional
import docker
from gefyra.api.utils import get_workload_type
from gefyra.exceptions import GefyraBridgeError, WorkloadNotFoundError
import kubernetes as k8s
from kubernetes.client.exceptions import ApiException
from kubernetes.config import load_kube_config

GEFYRA_APP_LABEL = "gefyra.dev/app"
STOWAWAY_PROXYROUTE_CONFIGMAPNAME = "gefyra-stowaway-proxyroutes"
BUSYBOX_COMMAND = "/bin/busybox"
CARRIER_CONFIGURE_PROBE_COMMAND_BASE = [BUSYBOX_COMMAND, "sh", "setprobe.sh"]
PROXY_RELOAD_COMMAND = [
    "/bin/bash",
    "generate-proxyroutes.sh",
    "/stowaway/proxyroutes/",
]
STOWAWAY_LABELS = {
    "gefyra.dev/app": "stowaway",
    "gefyra.dev/role": "connection",
    "gefyra.dev/provider": "stowaway",
}
CARRIER_IMAGE = "quay.io/gefyra/carrier2:latest"

load_kube_config()

core_v1_api = k8s.client.CoreV1Api()
apps_v1_api = k8s.client.AppsV1Api()


def get_label_selector(labels: dict[str, str]) -> str:
    return ",".join(["{0}={1}".format(*label) for label in list(labels.items())])


def _get_now() -> str:
    return datetime.utcnow().isoformat(timespec="microseconds") + "Z"


def create_stowaway_proxyroute_configmap() -> k8s.client.V1ConfigMap:
    configmap = k8s.client.V1ConfigMap(
        api_version="v1",
        kind="ConfigMap",
        data={},
        metadata=k8s.client.V1ObjectMeta(
            name=STOWAWAY_PROXYROUTE_CONFIGMAPNAME,
            namespace="gefyra",
            labels={"gefyra.dev/app": "stowaway", "gefyra.dev/role": "proxyroute"},
        ),
    )
    return configmap


def _get_free_proxyroute_port() -> int:
    _config = create_stowaway_proxyroute_configmap()
    configmap = core_v1_api.read_namespaced_config_map(
        _config.metadata.name, _config.metadata.namespace
    )
    routes = configmap.data
    # the values ar stored as "to_ip:to_port,proxy_port"
    if routes:
        taken_ports = [int(v.split(",")[1]) for v in routes.values()]
    else:
        taken_ports = []
    for port in range(10000, 60000):
        if port not in taken_ports:
            return port
    raise RuntimeError("No free port found for proxy route")


def _edit_proxyroutes_configmap(
    peer_id: str,
    add: Optional[str] = None,
    remove: Optional[str] = None,
) -> int:
    _config = create_stowaway_proxyroute_configmap()
    configmap = core_v1_api.read_namespaced_config_map(
        _config.metadata.name, _config.metadata.namespace
    )
    routes = configmap.data
    if routes is None:
        routes = {}
    if add:
        stowaway_port = _get_free_proxyroute_port()
        routes[f"{peer_id}-{''.join(random.choices(string.ascii_lowercase, k=10))}"] = (
            f"{add},{stowaway_port}"
        )
        core_v1_api.patch_namespaced_config_map(
            name=configmap.metadata.name,
            namespace=configmap.metadata.namespace,
            body={"data": routes},
        )
        return int(stowaway_port)
    elif remove:
        to_be_deleted = None
        stowaway_port = 0
        for k, v in routes.items():
            if v.split(",")[0] == remove:
                to_be_deleted = k
                stowaway_port = v.split(",")[1]
        if to_be_deleted:
            del routes[to_be_deleted]
            configmap.data = routes
            core_v1_api.replace_namespaced_config_map(
                name=configmap.metadata.name,
                namespace=configmap.metadata.namespace,
                body=configmap,
            )
        return int(stowaway_port)
    else:
        raise ValueError("Either the add or remove parameter must be set")


def create_stowaway_proxy_service(
    stowaway_deployment: k8s.client.V1Deployment, port: int, client_id: str = "unknown"
) -> k8s.client.V1Service:
    print(f"Creating stowaway proxy service for port {port}")
    spec = k8s.client.V1ServiceSpec(
        type="ClusterIP",
        selector=stowaway_deployment.spec.template.metadata.labels,
        cluster_ip="None",  # this is a headless service
        ports=[
            k8s.client.V1ServicePort(
                name=str(port),
                target_port=port,
                port=port,
            )
        ],
    )

    service = k8s.client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=k8s.client.V1ObjectMeta(
            name=f"gefyra-stowaway-proxy-{port}",
            namespace=stowaway_deployment.metadata.namespace,
            labels={
                GEFYRA_APP_LABEL: "stowaway",
                "gefyra.dev/role": "proxy",
                "gefyra.dev/proxy-port": str(port),
                "gefyra.dev/client-id": client_id,
            },
        ),
        spec=spec,
    )

    return service


def _notify_stowaway_pod(pod_name: str):
    core_v1_api.patch_namespaced_pod(
        name=pod_name,
        body={
            "metadata": {
                "annotations": {"operator": f"update-notification-{_get_now()}"}
            }
        },
        namespace="gefyra",
    )
    sleep(1)


def exec_command_pod(
    api_instance: k8s.client.CoreV1Api,
    pod_name: str,
    namespace: str,
    container_name: str,
    command: List[str],
) -> str:
    """
    Exec a command on a Pod and exit
    :param api_instance: a CoreV1Api instance
    :param pod_name: the name of the Pod to exec this command on
    :param namespace: the namespace this Pod is running in
    :param container_name: the container name of this Pod
    :param command: command as List[str]
    :return: the result output as str
    """
    print(f"Executing command {command} on pod {pod_name}, container {container_name}")
    resp = k8s.stream.stream(
        api_instance.connect_get_namespaced_pod_exec,
        pod_name,
        namespace,
        container=container_name,
        command=command,
        stderr=True,
        stdin=False,
        stdout=True,
        tty=False,
    )
    return resp


def _get_stowaway_pod() -> Optional[k8s.client.V1Pod]:
    stowaway_pod = core_v1_api.list_namespaced_pod(
        "gefyra",
        label_selector=get_label_selector(STOWAWAY_LABELS),
    )
    if stowaway_pod.items and len(stowaway_pod.items) > 0:
        return stowaway_pod.items[0]
    else:
        return None


def _add_destination(
    peer_id: str,
    destination_ip: str,
    destination_port: int,
):
    print(f"Adding destination {destination_ip}:{destination_port} for peer {peer_id}")
    stowaway_port = _edit_proxyroutes_configmap(
        peer_id=peer_id, add=f"{destination_ip}:{destination_port}"
    )
    stowaway = apps_v1_api.read_namespaced_stateful_set(
        name="gefyra-stowaway", namespace="gefyra"
    )
    # create a stowaway proxy k8s service (target of reverse proxy in bridge operations)
    svc = create_stowaway_proxy_service(
        stowaway_deployment=stowaway,
        port=stowaway_port,
        client_id=peer_id,
    )
    core_v1_api.create_namespaced_service(body=svc, namespace="gefyra")
    stowaway_pod = _get_stowaway_pod()
    if stowaway_pod is None:
        raise RuntimeError("No Stowaway Pod found for destination addition")
    _notify_stowaway_pod(stowaway_pod.metadata.name)
    exec_command_pod(
        core_v1_api,
        stowaway_pod.metadata.name,
        "gefyra",
        "stowaway",
        PROXY_RELOAD_COMMAND,
    )
    return f"{svc.metadata.name}.gefyra.svc.cluster.local:{stowaway_port}"


def get_pods_and_containers_for_workload(
    name: str, namespace: str, workload_type: str
) -> Dict[str, List[str]]:
    result = {}
    API_EXCEPTION_MSG = "Exception when calling Kubernetes API: {}"
    workload_type = get_workload_type(workload_type)
    NOT_FOUND_MSG = f"{workload_type.capitalize()} not found."
    try:
        if workload_type == "deployment":
            workload = apps_v1_api.read_namespaced_deployment(
                name=name, namespace=namespace
            )
        elif workload_type == "statefulset":
            workload = apps_v1_api.read_namespaced_stateful_set(
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
    pods = core_v1_api.list_namespaced_pod(
        namespace=namespace, label_selector=label_selector
    )

    for pod in pods.items:
        result[pod.metadata.name] = [
            container.name for container in pod.spec.containers
        ]
    return result


def _get_all_probes(container: k8s.client.V1Container) -> List[k8s.client.V1Probe]:
    probes = []
    if container.startup_probe:
        probes.append(container.startup_probe)
    if container.readiness_probe:
        probes.append(container.readiness_probe)
    if container.liveness_probe:
        probes.append(container.liveness_probe)
    return probes


def _ensure_probes(container: k8s.client.V1Container, pod, namespace) -> bool:
    probes = _get_all_probes(container)
    for probe in probes:
        try:
            command = CARRIER_CONFIGURE_PROBE_COMMAND_BASE + [
                probe.http_get.port,
            ]
            exec_command_pod(core_v1_api, pod, namespace, container.name, command)
        except Exception as e:
            print(e)
            return False
    return True


def _patch_workload(deployment_name: str, namespace: str, container_name: str):
    pods = get_pods_and_containers_for_workload(
        deployment_name, namespace, "deployment"
    )
    pod_names = pods.keys()

    for pod_name in pod_names:
        pod = core_v1_api.read_namespaced_pod(
            name=pod_name,
            namespace=namespace,
        )
        for container in pod.spec.containers:
            if container.name == container_name:
                container.image = CARRIER_IMAGE
                break
        core_v1_api.patch_namespaced_pod(
            name=pod.metadata.name,
            namespace=namespace,
            body=pod,
        )
        counter = 0
        while not _ensure_probes(container, pod.metadata.name, namespace):
            if counter >= 100:
                print("Could not ensure probes. Exiting.")
                exit(1)
            counter += 1
            sleep(1)


def create_reverse_service(
    name: str, ports: Dict[str, str], client_id: str, network: str
):
    from docker.errors import NotFound

    docker_client = docker.from_env()

    try:
        container = docker_client.containers.get(name)
    except NotFound:
        raise GefyraBridgeError(f"Could not find target container '{name}'")

    port_mappings = [f"{key}:{value}" for key, value in ports.items()]
    print(port_mappings)

    try:
        local_container_ip = container.attrs["NetworkSettings"]["Networks"][network][
            "IPAddress"
        ]
    except KeyError:
        raise GefyraBridgeError(
            f"The target container '{name}' is not in Gefyra's network"
            f"{network}. Did you run 'gefyra up'?"
        ) from None

    for port_mapping in port_mappings:
        source_port, target_port = port_mapping.split(":")
        _add_destination(client_id, local_container_ip, int(source_port))
