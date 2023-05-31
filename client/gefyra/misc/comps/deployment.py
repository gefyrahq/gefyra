# flake8: noqa
from gefyra.types import GefyraInstallOptions


def data(params: GefyraInstallOptions) -> list[dict]:
    return [
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "gefyra-operator",
                "namespace": params.namespace,
                "labels": {
                    "gefyra.dev/app": "gefyra-operator",
                    "gefyra.dev/role": "operator",
                },
            },
            "spec": {
                "replicas": 1,
                "selector": {
                    "matchLabels": {
                        "gefyra.dev/app": "gefyra-operator",
                        "gefyra.dev/role": "operator",
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "gefyra.dev/app": "gefyra-operator",
                            "gefyra.dev/role": "operator",
                        }
                    },
                    "spec": {
                        "serviceAccountName": "gefyra-operator",
                        "containers": [
                            {
                                "name": "gefyra",
                                "image": f"quay.io/gefyra/operator:{params.version}",
                                "imagePullPolicy": "Always",
                                "ports": [{"containerPort": 9443}],
                            }
                        ],
                    },
                },
            },
        },
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "gefyra-operator-webhook",
                "namespace": params.namespace,
                "labels": {
                    "gefyra.dev/app": "gefyra-operator",
                    "gefyra.dev/role": "webhook",
                },
            },
            "spec": {
                "replicas": 1,
                "selector": {
                    "matchLabels": {
                        "gefyra.dev/app": "gefyra-operator",
                        "gefyra.dev/role": "webhook",
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "gefyra.dev/app": "gefyra-operator",
                            "gefyra.dev/role": "webhook",
                        }
                    },
                    "spec": {
                        "serviceAccountName": "gefyra-operator",
                        "containers": [
                            {
                                "name": "gefyra",
                                "image": f"quay.io/gefyra/operator:{params.version}",
                                "imagePullPolicy": "Always",
                                "ports": [{"containerPort": 9443}],
                                "env": [{"name": "OP_MODE", "value": "webhook"}],
                            }
                        ],
                    },
                },
            },
        },
    ]
