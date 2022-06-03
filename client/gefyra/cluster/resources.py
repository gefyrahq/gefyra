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
)

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


def get_pods_and_containers_for_workload(
    config: ClientConfiguration, name: str, namespace: str
) -> Dict[str, List[str]]:
    result = {}
    name = name.split("-")
    pods = config.K8S_CORE_API.list_namespaced_pod(namespace)
    for pod in pods.items:
        pod_name = pod.metadata.name.split("-")
        if all(x == y for x, y in zip(name, pod_name)) and len(pod_name) - 2 == len(
            name
        ):
            # this pod name containers all segments of name
            result[pod.metadata.name] = [
                container.name for container in pod.spec.containers
            ]
    return result
