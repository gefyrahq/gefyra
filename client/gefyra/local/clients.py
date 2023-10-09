import time

import logging
from gefyra.configuration import ClientConfiguration
from gefyra.exceptions import (
    GefyraClientAlreadyExists,
    GefyraClientNotFound,
    GefyraConnectionError,
)

logger = logging.getLogger(__name__)


def handle_create_gefyraclient(config: ClientConfiguration, body) -> dict:
    from kubernetes.client import ApiException

    retries = 15
    counter = 0
    success = False
    while not success:
        try:
            gclient = config.K8S_CUSTOM_OBJECT_API.create_namespaced_custom_object(
                namespace=config.NAMESPACE,
                body=body,
                group="gefyra.dev",
                plural="gefyraclients",
                version="v1",
            )
            success = True
        except ApiException as e:
            if e.status == 409:
                raise GefyraClientAlreadyExists(
                    f"Client {body['metadata']['name']} already exists."
                )
            logger.error(
                f"A Kubernetes API Error occured. \nReason:{e.reason} \nBody:{e.body}"
            )
            if counter < retries:
                counter += 1
                time.sleep(4)
            else:
                raise e
    return gclient


def handle_get_gefyraclient(config: ClientConfiguration, client_id: str) -> dict:
    from kubernetes.client import ApiException
    import urllib3

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
            raise GefyraClientNotFound(f"Client {client_id} does not exist.")
        else:
            logger.error(
                f"A Kubernetes API Error occured. \nReason:{e.reason} \nBody:{e.body}"
            )
            raise e
    except urllib3.exceptions.MaxRetryError as e:
        # this connection does not work (at the moment)
        raise GefyraConnectionError(
            f"This connection does not work. Is the cluster at {e.pool.host}:{e.pool.port} reachable? "
            f"Is the client '{client_id}' stale (e.g. from an old connection)? "
            f"Remove it with 'gefyra connection remove {client_id}' and try again."
        )

    return gclient


def handle_delete_gefyraclient(
    config: ClientConfiguration, client_id: str, force: bool, wait: bool = False
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
        if wait:
            timeout = 30
            counter = 0
            while counter < timeout:
                try:
                    handle_get_gefyraclient(config=config, client_id=client_id)
                except GefyraClientNotFound:
                    return True
                time.sleep(1)
                counter += 1
            return False
        return True
    except ApiException as e:
        logger.debug(e)
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
            "namespace": config.NAMESPACE,
        },
        "provider": provider,
    }
