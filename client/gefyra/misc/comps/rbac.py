# flake8: noqa
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gefyra.types import GefyraInstallOptions


def data(params: "GefyraInstallOptions") -> list[dict]:
    return [
        {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {"namespace": params.namespace, "name": "gefyra-operator"},
        },
        {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRole",
            "metadata": {"name": "gefyra:operator"},
            "rules": [
                {
                    "apiGroups": ["kopf.dev"],
                    "resources": ["clusterkopfpeerings"],
                    "verbs": ["list", "watch", "patch", "get"],
                },
                {
                    "apiGroups": ["apiextensions.k8s.io"],
                    "resources": ["customresourcedefinitions"],
                    "verbs": ["create", "patch", "delete", "list", "watch"],
                },
                {
                    "apiGroups": ["admissionregistration.k8s.io"],
                    "resources": [
                        "validatingwebhookconfigurations",
                        "mutatingwebhookconfigurations",
                    ],
                    "verbs": ["create", "patch"],
                },
                {
                    "apiGroups": [
                        "",
                        "apps",
                        "batch",
                        "extensions",
                        "events.k8s.io",
                        "rbac.authorization.k8s.io",
                        "rbac.authorization.k8s.io/v1",
                    ],
                    "resources": [
                        "namespaces",
                        "clusterroles",
                        "serviceaccounts",
                        "clusterrolebindings",
                        "nodes",
                        "configmaps",
                        "secrets",
                        "deployments",
                        "statefulsets",
                        "persistentvolumeclaims",
                        "services",
                        "pods",
                        "pods/exec",
                        "events",
                    ],
                    "verbs": ["*"],
                },
                {
                    "apiGroups": ["gefyra.dev"],
                    "resources": ["gefyraclients", "gefyrabridges"],
                    "verbs": ["*"],
                },
            ],
        },
        {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRoleBinding",
            "metadata": {
                "name": "gefyra-operator",
                "namespace": params.namespace,
            },
            "roleRef": {
                "apiGroup": "rbac.authorization.k8s.io",
                "kind": "ClusterRole",
                "name": "gefyra:operator",
            },
            "subjects": [
                {
                    "kind": "ServiceAccount",
                    "name": "gefyra-operator",
                    "namespace": params.namespace,
                }
            ],
        },
    ]
