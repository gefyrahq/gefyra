import logging
from typing import List, Dict

from kubernetes.client import (
    V1ServiceAccount,
    V1ObjectMeta,
    V1ClusterRole,
    V1PolicyRule,
    V1ClusterRoleBinding,
    V1RoleRef,
    V1Subject,
    V1PodTemplateSpec,
    V1Deployment,
    V1PodSpec,
    V1Container,
    V1EnvVar,
    V1DeploymentSpec,
    ApiException,
    V1Pod,
)

from gefyra.api.utils import get_workload_type
from gefyra.configuration import ClientConfiguration

logger = logging.getLogger(__name__)


def create_operator_serviceaccount(namespace: str) -> V1ServiceAccount:
    return V1ServiceAccount(
        metadata=V1ObjectMeta(
            # this name is referenced by Operator
            name="gefyra-operator",
            namespace=namespace,
        )
    )


def create_operator_clusterrole() -> V1ClusterRole:
    crd_rule = V1PolicyRule(
        api_groups=["apiextensions.k8s.io"],
        resources=["customresourcedefinitions"],
        verbs=["create", "patch", "delete", "list", "watch"],
    )
    kopf_rules = V1PolicyRule(
        api_groups=["kopf.dev"],
        resources=["clusterkopfpeerings"],
        verbs=["create", "patch"],
    )
    misc_res_rule = V1PolicyRule(
        api_groups=["", "apps", "extensions", "events.k8s.io"],
        resources=[
            "namespaces",
            "configmaps",
            "secrets",
            "deployments",
            "services",
            "serviceaccounts",
            "pods",
            "pods/exec",
            "events",
        ],
        verbs=["create", "patch", "update", "delete", "get", "list"],
    )
    ireq_rule = V1PolicyRule(
        api_groups=["gefyra.dev"], resources=["interceptrequests"], verbs=["*"]
    )

    clusterrole = V1ClusterRole(
        kind="ClusterRole",
        metadata=V1ObjectMeta(
            # this name is referenced by Operator
            name="gefyra-operator-role",
        ),
        rules=[
            crd_rule,
            kopf_rules,
            # kopf_peering,
            misc_res_rule,
            ireq_rule,
        ],
    )
    return clusterrole


def create_operator_clusterrolebinding(
    serviceaccount: V1ServiceAccount,
    clusterrole: V1ClusterRole,
    namespace: str,
) -> V1ClusterRoleBinding:
    return V1ClusterRoleBinding(
        metadata=V1ObjectMeta(
            # this name is referenced by Operator
            name="gefyra-operator-rolebinding",
        ),
        role_ref=V1RoleRef(
            api_group="rbac.authorization.k8s.io",
            name=clusterrole.metadata.name,
            kind="ClusterRole",
        ),
        subjects=[
            V1Subject(
                kind="ServiceAccount",
                name=serviceaccount.metadata.name,
                namespace=namespace,
            )
        ],
    )


def create_operator_deployment(
    serviceaccount: V1ServiceAccount,
    config: ClientConfiguration,
    gefyra_network_subnet: str,
) -> V1Deployment:
    template = V1PodTemplateSpec(
        metadata=V1ObjectMeta(labels={"app": "gefyra-operator"}),
        spec=V1PodSpec(
            containers=[
                V1Container(
                    name="gefyra-operator",
                    image=config.OPERATOR_IMAGE,
                    env=[
                        V1EnvVar(
                            name="GEFYRA_PEER_SUBNET", value=gefyra_network_subnet
                        ),
                        V1EnvVar(
                            name="GEFYRA_STOWAWAY_IMAGE",
                            value=config.STOWAWAY_IMAGE.split(":")[0],
                        ),
                        V1EnvVar(
                            name="GEFYRA_STOWAWAY_TAG",
                            value=config.STOWAWAY_IMAGE.split(":")[1],
                        ),
                        V1EnvVar(
                            name="GEFYRA_CARRIER_IMAGE",
                            value=config.CARRIER_IMAGE.split(":")[0],
                        ),
                        V1EnvVar(
                            name="GEFYRA_CARRIER_TAG",
                            value=config.CARRIER_IMAGE.split(":")[1],
                        ),
                    ],
                )
            ],
            service_account_name=serviceaccount.metadata.name,
        ),
    )
    spec = V1DeploymentSpec(
        replicas=1,
        template=template,
        selector={"matchLabels": {"app": "gefyra-operator"}},
    )
    deployment = V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=V1ObjectMeta(name="gefyra-operator", namespace=config.NAMESPACE),
        spec=spec,
    )

    return deployment


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
                f"Cannot bridge pod {pod.metadata.name} since it has a `command` defined."
            )


def check_pod_valid_for_bridge(
    config: ClientConfiguration, pod_name: str, namespace: str, container_name: str
):
    pod = config.K8S_CORE_API.read_namespaced_pod(
        name=pod_name,
        namespace=namespace,
    )

    _check_pod_for_command(pod, container_name)


def get_pods_and_containers_for_workload(
    config: ClientConfiguration, name: str, namespace: str, workload_type: str
) -> Dict[str, List[str]]:
    workload = None
    result = {}
    API_EXCEPTION_MSG = "Exception when calling Kubernetes API: {}"
    NOT_FOUND_MSG = f"{workload_type.capitalize()} not found."
    workload_type = get_workload_type(workload_type)
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
            raise RuntimeError(NOT_FOUND_MSG)
        raise RuntimeError(API_EXCEPTION_MSG.format(e))

    if not workload:
        raise RuntimeError(f"Could not find {workload_type} - {name}.")
    v1_label_selector = workload.spec.selector.match_labels

    label_selector = ",".join(
        [f"{key}={value}" for key, value in v1_label_selector.items()]
    )

    if not label_selector:
        raise RuntimeError(f"No label selector set for {workload_type} - {name}.")

    pods = config.K8S_CORE_API.list_namespaced_pod(
        namespace=namespace, label_selector=label_selector
    )
    for pod in pods.items:
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
        raise RuntimeError(API_EXCEPTION_MSG.format(e))
    if not pod.spec:  # `.spec` is optional in python kubernetes client
        raise RuntimeError(f"Could not retrieve spec for pod - {name}.")
    result[pod.metadata.name] = [container.name for container in pod.spec.containers]
    return result
