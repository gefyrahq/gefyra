# flake8: noqa
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gefyra.types import GefyraInstallOptions

STOWAWAY_LABELS = {
    "gefyra.dev/app": "stowaway",
    "gefyra.dev/role": "connection",
    "gefyra.dev/provider": "stowaway",
}


def data(params: "GefyraInstallOptions") -> list[dict]:
    stowaway_labels = STOWAWAY_LABELS.copy()
    stowaway_annotations = {}
    if params.service_labels:
        try:
            stowaway_labels.update(params.service_labels)
        except IndexError:
            raise ValueError(
                f"Invalid service-labels format. Please use the form key=value."
            )
    if params.service_annotations:
        try:
            stowaway_annotations.update(params.service_annotations)
        except IndexError:
            raise ValueError(
                f"Invalid service-annotations format. Please use the form key=value."
            )
    if params.service_type.lower() == "nodeport":
        type = "NodePort"
        ports = [
            {
                "name": "gefyra-wireguard",
                "port": 51820,
                "targetPort": 51820,
                "nodePort": params.service_port,
                "protocol": "UDP",
            }
        ]
    elif params.service_type.lower() == "loadbalancer":
        type = "LoadBalancer"
        ports = [
            {
                "name": "gefyra-wireguard",
                "port": params.service_port,
                "targetPort": 51820,
                "protocol": "UDP",
            }
        ]
    else:
        raise ValueError(f"Unknown service type: {params.service_type}")
    return [
        {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "gefyra-stowaway-wireguard",
                "namespace": params.namespace,
                "labels": stowaway_labels,
                "annotations": stowaway_annotations,
            },
            "spec": {
                "type": type,
                "ports": ports,
                "selector": STOWAWAY_LABELS,
            },
        }
    ]
