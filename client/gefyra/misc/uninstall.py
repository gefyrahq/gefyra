import kubernetes as k8s

from gefyra.configuration import ClientConfiguration
from gefyra import api


def remove_all_clients(config: ClientConfiguration):
    clients = api.list_client(config=config)
    for client in clients:
        api.delete_client(client.client_id, config=config)


def remove_remainder_bridges(config: ClientConfiguration):
    try:
        gbridges = config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object(
            group="gefyra.dev",
            version="v1",
            namespace=config.NAMESPACE,
            plural="gefyrabridges",
        )
    except Exception:
        return None
    for bridge in gbridges.get("items"):
        try:
            config.K8S_CUSTOM_OBJECT_API.patch_namespaced_custom_object(
                group="gefyra.dev",
                version="v1",
                plural="gefyrabridges",
                namespace=config.NAMESPACE,
                name=bridge["metadata"]["name"],
                body={"metadata": {"finalizers": None}},
            )
            config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object(
                group="gefyra.dev",
                version="v1",
                plural="gefyrabridges",
                namespace=config.NAMESPACE,
                name=bridge["metadata"]["name"],
            )
        except Exception:
            continue
    return None

def remove_gefyra_namespace(config: ClientConfiguration):
    try:
        config.K8S_CORE_API.delete_namespace(name=config.NAMESPACE)
    except k8s.client.exceptions.ApiException as e:  # type: ignore
        if e.status == 404:
            return
        else:
            raise e from None
