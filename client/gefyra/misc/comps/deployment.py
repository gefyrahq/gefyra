# flake8: noqa
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gefyra.types import GefyraInstallOptions


def data(params: "GefyraInstallOptions") -> list[dict]:
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
                                "image": f"{params.registry}/operator:{params.version}",
                                "imagePullPolicy": "IfNotPresent",
                                "ports": [{"containerPort": 9443}],
                                "env": [
                                    {
                                        "name": "GEFYRA_STOWAWAY_IMAGE",
                                        "value": f"{params.registry}/stowaway",
                                    },
                                    {
                                        "name": "GEFYRA_STOWAWAY_TAG",
                                        "value": params.version,
                                    },
                                    {
                                        "name": "GEFYRA_CARRIER_IMAGE",
                                        "value": f"{params.registry}/carrier",
                                    },
                                    {
                                        "name": "GEFYRA_CARRIER_IMAGE_TAG",
                                        "value": params.version,
                                    },
                                    {
                                        "name": "GEFYRA_STOWAWAY_STORAGE",
                                        "value": str(params.stowaway_storage),
                                    },
                                ],
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
                                "image": f"{params.registry}/operator:{params.version}",
                                "imagePullPolicy": "IfNotPresent",
                                "ports": [{"containerPort": 9443}],
                                "env": [
                                    {"name": "OP_MODE", "value": "webhook"},
                                    {
                                        "name": "GEFYRA_STOWAWAY_IMAGE",
                                        "value": f"{params.registry}/stowaway",
                                    },
                                    {
                                        "name": "GEFYRA_STOWAWAY_TAG",
                                        "value": params.version,
                                    },
                                    {
                                        "name": "GEFYRA_CARRIER_IMAGE",
                                        "value": f"{params.registry}/carrier",
                                    },
                                    {
                                        "name": "GEFYRA_CARRIER_IMAGE_TAG",
                                        "value": params.version,
                                    },
                                    {
                                        "name": "GEFYRA_STOWAWAY_STORAGE",
                                        "value": str(params.stowaway_storage),
                                    },
                                ],
                                "livenessProbe": {
                                    "exec": {
                                        "command": [
                                            "python",
                                            "gefyra/healthcheck.py",
                                        ]
                                    },
                                    "initialDelaySeconds": 5,
                                    "periodSeconds": 5,
                                    "timeoutSeconds": 3,
                                },
                            }
                        ],
                    },
                },
            },
        },
    ]
