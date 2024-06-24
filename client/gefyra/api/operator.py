from pathlib import Path
from typing import Optional
from gefyra.api.utils import stopwatch
from gefyra.configuration import ClientConfiguration, __VERSION__
from gefyra.exceptions import ClusterError


@stopwatch
def update(
    version: Optional[str] = None,
    kubeconfig: Optional[Path] = None,
    kubecontext: Optional[str] = None,
) -> bool:
    # update operator deployment to latest version

    config = ClientConfiguration(kube_config_file=kubeconfig, kube_context=kubecontext)
    if not version:
        version = __VERSION__

    try:
        ns = config.K8S_CORE_API.read_namespaced_namespace(name=config.NAMESPACE)
        if ns.status.phase.lower() != "active":
            raise ClusterError(
                f"Cannot update Gefyra operator: namespace {config.NAMESPACE} is in {ns.status.phase} state"
            )
    except:  # noqa
        pass

    names = ["gefyra-operator", "gefyra-operator-webhook"]
    for name in names:
        config.K8S_APP_API.patch_namespaced_deployment(
            name=name,
            namespace=config.NAMESPACE,
            body={
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "gefyra",
                                    "image": f"quay.io/gefyra/operator:{version}",
                                }
                            ]
                        }
                    }
                }
            },
        )
        config.K8S_APP_API.patch_namespaced_deployment(
            name=name,
            namespace=config.NAMESPACE,
            body={
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "gefyra",
                                    "env": [
                                        {
                                            "name": "GEFYRA_STOWAWAY_TAG",
                                            "value": version,
                                        }
                                    ],
                                }
                            ]
                        }
                    }
                }
            },
        )
        config.K8S_APP_API.patch_namespaced_deployment(
            name=name,
            namespace=config.NAMESPACE,
            body={
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "gefyra",
                                    "env": [
                                        {
                                            "name": "GEFYRA_CARRIER_IMAGE_TAG",
                                            "value": version,
                                        }
                                    ],
                                }
                            ]
                        }
                    }
                }
            },
        )

    return True
