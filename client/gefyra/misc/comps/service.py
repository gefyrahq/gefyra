# flake8: noqa
from gefyra.types import GefyraInstallOptions

STOWAWAY_LABELS = {
    "gefyra.dev/app": "stowaway",
    "gefyra.dev/role": "connection",
    "gefyra.dev/provider": "stowaway",
}

def data(params: GefyraInstallOptions) -> list[dict]:
    stowaway_labels = STOWAWAY_LABELS.copy()
    stowaway_labels.update(params.service_labels)
    if params.service_type.lower() == "nodeport":
        type = "NodePort"
    elif params.service_type.lower() == "loadbalancer":
        type = "LoadBalancer"
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
                "annotations": params.service_annotations,
            },
            "spec": {
                "type": type,
                "ports": [{"name": "gefyra-wireguard", "port": 51820, "targetPort": 51820, "nodePort": params.service_port, "protocol": "UDP"}],
                "selector": STOWAWAY_LABELS,
            },
        }
    ]
        