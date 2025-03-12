import logging

from gefyra.configuration import ClientConfiguration

logger = logging.getLogger(__name__)


def handle_create_gefyrabridgemount(config: ClientConfiguration, body, target: str):
    from kubernetes.client import ApiException

    try:
        mount = config.K8S_CUSTOM_OBJECT_API.create_namespaced_custom_object(
            namespace=config.NAMESPACE,
            body=body,
            group="gefyra.dev",
            plural="gefyrabridgemounts",
            version="v1",
        )
    except ApiException as e:
        if e.status == 409:
            raise RuntimeError(f"Workload {target} already bridged.")
        logger.error(
            f"A Kubernetes API Error occured. \nReason: {e.reason} \nBody: {e.body}"
        )
        raise e from None
    return mount


def get_gbridgemount_body(
    config: ClientConfiguration,
    name: str,
    target,
    target_namespace,
    target_container,
) -> dict[str, str | dict[str, str]]:
    return {
        "apiVersion": "gefyra.dev/v1",
        "kind": "gefyrabridgeount",
        "metadata": {
            "name": name,
            "namespace": config.NAMESPACE,
        },
        "targetNamespace": target_namespace,
        "target": target,
        "targetContainer": target_container,
        "provider": "carrier2",
        "providerParameter": {},
    }


def get_all_gefyrabridgemounts(
    config: ClientConfiguration,
) -> list[dict[str, str | dict[str, str]]]:
    from kubernetes.client import ApiException

    try:
        ireq_list = config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object(
            namespace=config.NAMESPACE,
            group="gefyra.dev",
            plural="gefyrabridgemounts",
            version="v1",
        )
        if ireq_list:
            # filter bridges for this client
            return list(
                item
                for item in ireq_list.get("items")
                if item["client"] == config.CLIENT_ID
            )
        else:
            return []
    except ApiException as e:
        if e.status != 404:
            logger.warning("Error getting GefyraBridgeMounts: " + str(e))
            raise e from None
        return []
