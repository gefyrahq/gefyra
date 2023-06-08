# flake8: noqa
from gefyra.types import GefyraInstallOptions

STOWAWAY_LABELS = {
    "gefyra.dev/app": "stowaway",
    "gefyra.dev/role": "connection",
    "gefyra.dev/provider": "stowaway",
}


def data(params: GefyraInstallOptions) -> list[dict]:
    stowaway_labels = STOWAWAY_LABELS.copy()
    stowaway_annotations = {}
    if params.service_labels:
        from ast import literal_eval as make_tuple

        try:
            labels = [make_tuple(k)[0] for k in params.service_labels]
            stowaway_labels.update(
                {label.split("=")[0]: label.split("=")[1] for label in labels}
            )
        except IndexError:
            raise ValueError(
                f"Invalid service-labels format. Please use the form key=value."
            )
    if params.service_annotations:
        from ast import literal_eval as make_tuple

        try:
            annotations = [make_tuple(k)[0] for k in params.service_annotations]
            stowaway_annotations.update(
                {
                    annotation.split("=")[0]: annotation.split("=")[1]
                    for annotation in annotations
                }
            )
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
