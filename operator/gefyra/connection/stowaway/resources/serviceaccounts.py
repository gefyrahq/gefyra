import kubernetes as k8s
from gefyra.configuration import configuration


def create_stowaway_serviceaccount() -> k8s.client.V1ServiceAccount:
    return k8s.client.V1ServiceAccount(
        metadata=k8s.client.V1ObjectMeta(
            # this name is referenced by Stowaway
            name="gefyra-stowaway",
            namespace=configuration.NAMESPACE,
            labels={"gefyra.dev/app": "stowaway"},
        )
    )
