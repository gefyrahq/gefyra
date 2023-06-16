import logging
from gefyra.configuration import ClientConfiguration
from gefyra.exceptions import GefyraClientAlreadyExists, GefyraClientNotFound

logger = logging.getLogger(__name__)


def handle_create_gefyraclient(config: ClientConfiguration, body) -> dict:
    from kubernetes.client import ApiException

    try:
        gclient = config.K8S_CUSTOM_OBJECT_API.create_namespaced_custom_object(
            namespace=config.NAMESPACE,
            body=body,
            group="gefyra.dev",
            plural="gefyraclients",
            version="v1",
        )
    except ApiException as e:
        if e.status == 409:
            raise GefyraClientAlreadyExists(
                f"Client {body['metadata']['name']} already exists."
            )
        logger.error(
            f"A Kubernetes API Error occured. \nReason:{e.reason} \nBody:{e.body}"
        )
        raise e
    return gclient


def handle_get_gefyraclient(config: ClientConfiguration, client_id: str) -> dict:
    from kubernetes.client import ApiException

    try:
        gclient = config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object(
            namespace=config.NAMESPACE,
            name=client_id,
            group="gefyra.dev",
            plural="gefyraclients",
            version="v1",
        )
    except ApiException as e:
        if e.status in [404, 403]:
            raise GefyraClientNotFound(f"Client {client_id} does not exists.")
        else:
            logger.error(
                f"A Kubernetes API Error occured. \nReason:{e.reason} \nBody:{e.body}"
            )
            raise e
    return gclient


def handle_delete_gefyraclient(
    config: ClientConfiguration, client_id: str, force: bool
) -> bool:
    from kubernetes.client import ApiException

    try:
        if force:
            config.K8S_CUSTOM_OBJECT_API.patch_namespaced_custom_object(
                namespace=config.NAMESPACE,
                name=client_id,
                group="gefyra.dev",
                plural="gefyraclients",
                version="v1",
                body={"metadata": {"finalizers": None}},
            )
        config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object(
            namespace=config.NAMESPACE,
            name=client_id,
            group="gefyra.dev",
            plural="gefyraclients",
            version="v1",
        )
        return True
    except ApiException as e:
        if e.status in [404, 403]:
            return False
        else:
            logger.error(
                f"A Kubernetes API Error occured. \nReason:{e.reason} \nBody:{e.body}"
            )
            raise e


def get_gefyraclient_body(
    config: ClientConfiguration, client_id: str, provider: str = "stowaway"
) -> dict:
    return {
        "apiVersion": "gefyra.dev/v1",
        "kind": "gefyraclient",
        "metadata": {
            "name": client_id,
            "namspace": config.NAMESPACE,
        },
        "provider": provider,
    }
