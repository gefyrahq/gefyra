import logging

from gefyra.configuration import ClientConfiguration

logger = logging.getLogger(__name__)


def remove_all_clients():
    from gefyra.api.clients import delete_client, list_client

    clients = list_client()
    for client in clients:
        delete_client(client.client_id, force=True, wait=True)


def remove_remainder_bridge_mounts(config: ClientConfiguration):
    from kubernetes.client import ApiException

    try:
        mounts = config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object(
            group="gefyra.dev",
            version="v1",
            namespace=config.NAMESPACE,
            plural="gefyrabridgemounts",
        )
    except ApiException as e:
        logger.debug("Could not list Gefyra bridge mounts: %s", e)
        return
    for mount in mounts.get("items"):
        try:
            config.K8S_CUSTOM_OBJECT_API.patch_namespaced_custom_object(
                group="gefyra.dev",
                version="v1",
                plural="gefyrabridgemounts",
                namespace=config.NAMESPACE,
                name=mount["metadata"]["name"],
                body={"metadata": {"finalizers": None}},
            )
            config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object(
                group="gefyra.dev",
                version="v1",
                plural="gefyrabridgemounts",
                namespace=config.NAMESPACE,
                name=mount["metadata"]["name"],
            )
        except ApiException as e:
            logger.debug(
                "Could not remove GefyraBridgeMount '%s': %s",
                mount["metadata"].get("name", "<unknown>"),
                e,
            )
            continue
    return


def remove_remainder_bridges(config: ClientConfiguration):
    from kubernetes.client import ApiException

    try:
        gbridges = config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object(
            group="gefyra.dev",
            version="v1",
            namespace=config.NAMESPACE,
            plural="gefyrabridges",
        )
    except ApiException as e:
        logger.debug("Could not list Gefyra bridges: %s", e)
        return
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
        except ApiException as e:
            logger.debug(
                "Could not remove GefyraBridge '%s': %s",
                bridge["metadata"].get("name", "<unknown>"),
                e,
            )
            continue
    return


def remove_gefyra_namespace(config: ClientConfiguration):
    import kubernetes

    try:
        config.K8S_CORE_API.delete_namespace(name=config.NAMESPACE)
    except kubernetes.client.exceptions.ApiException as e:  # type: ignore
        if e.status == 404:
            return
        else:
            raise e from None


def remove_gefyra_crds(config: ClientConfiguration):
    import kubernetes

    crds = [
        "gefyrabridges.gefyra.dev",
        "gefyraclients.gefyra.dev",
        "gefyrabridgemounts.gefyra.dev",
    ]
    for crd in crds:
        try:
            config.K8S_EXTENSION_API.delete_custom_resource_definition(name=crd)
        except kubernetes.client.exceptions.ApiException:  # type: ignore
            pass


def remove_gefyra_rbac(config: ClientConfiguration):
    import kubernetes

    clusterroles = ["gefyra:operator"]
    clusterrolebindings = ["gefyra-operator"]
    webhooks = ["gefyra.dev"]
    for cr in clusterroles:
        try:
            config.K8S_RBAC_API.delete_cluster_role(name=cr)
        except kubernetes.client.exceptions.ApiException as e:  # type: ignore
            logger.debug(e)
    for crb in clusterrolebindings:
        try:
            config.K8S_RBAC_API.delete_cluster_role_binding(name=crb)
        except kubernetes.client.exceptions.ApiException as e:  # type: ignore
            logger.debug(e)
    for wh in webhooks:
        try:
            config.K8S_ADMISSION_API.delete_validating_webhook_configuration(name=wh)
        except kubernetes.client.exceptions.ApiException as e:
            logger.debug(e)
