import logging
import time
from typing import Optional

from gefyra.types import GefyraBridgeMount
from gefyra.configuration import ClientConfiguration

logger = logging.getLogger(__name__)


def handle_create_gefyrabridgemount(config: ClientConfiguration, body, target: str):
    from kubernetes.client import ApiException

    try:
        # TODO check if target already exists
        mount = config.K8S_CUSTOM_OBJECT_API.create_namespaced_custom_object(
            namespace=config.NAMESPACE,
            body=body,
            group="gefyra.dev",
            plural="gefyrabridgemounts",
            version="v1",
        )
    except ApiException as e:
        if e.status == 409:
            raise RuntimeError(
                f"GefyraBridgeMount '{body['metadata']['name']}' already exists"
            )
        logger.error(
            f"A Kubernetes API Error occured. \nReason: {e.reason} \nBody: {e.body}"
        )
        raise e from None
    return mount


def handle_delete_gefyramount(
    config: ClientConfiguration, name: str, force: bool, wait: bool
) -> bool:
    from kubernetes.client import ApiException

    try:
        if force:
            config.K8S_CUSTOM_OBJECT_API.patch_namespaced_custom_object(
                namespace=config.NAMESPACE,
                name=name,
                group="gefyra.dev",
                plural="gefyrabridgemounts",
                version="v1",
                body={"metadata": {"finalizers": None}},
            )
        config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object(
            namespace=config.NAMESPACE,
            name=name,
            group="gefyra.dev",
            plural="gefyrabridgemounts",
            version="v1",
        )
        if wait:
            timeout = 30
            counter = 0
            while counter < timeout:
                try:
                    get_gefyrabridgemount(config=config, name=name)
                except ApiException:
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


def get_tls_config(
    tls_certificate: Optional[str] = None,
    tls_key: Optional[str] = None,
    tls_sni: Optional[str] = None,
) -> dict[str, dict[str, str]]:
    if not tls_certificate and not tls_key:
        return {}
    if tls_certificate is None or tls_key is None:
        raise RuntimeError(
            "TLS configuration requires both certificate and key to be set."
        )
    res = {
        "tls": {
            "certificate": tls_certificate,
            "key": tls_key,
        }
    }
    if res and tls_sni is not None:
        res["tls"]["sni"] = tls_sni
    return res


def get_gbridgemount_body(
    config: ClientConfiguration,
    name: str,
    target: str,
    target_namespace: str,
    target_container: str,
    tls_certificate: Optional[str] = None,
    tls_key: Optional[str] = None,
    tls_sni: Optional[str] = None,
) -> dict[str, str | dict[str, dict[str, str]] | dict[str, str]]:
    return {
        "apiVersion": "gefyra.dev/v1",
        "kind": "gefyrabridgemount",
        "metadata": {
            "name": name,
            "namespace": config.NAMESPACE,
        },
        "targetNamespace": target_namespace,
        "target": target,
        "targetContainer": target_container,
        "provider": "carrier2",
        "providerParameter": get_tls_config(
            tls_certificate=tls_certificate,
            tls_key=tls_key,
            tls_sni=tls_sni,
        ),
    }


def get_gefyrabridgemount(config: ClientConfiguration, name: str) -> GefyraBridgeMount:
    from kubernetes.client import ApiException

    try:
        mount = config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object(
            name=name,
            namespace=config.NAMESPACE,
            group="gefyra.dev",
            plural="gefyrabridgemounts",
            version="v1",
        )
        return GefyraBridgeMount(mount)
    except ApiException as e:
        if e.status != 404:
            logger.warning("Error getting GefyraBridgeMounts: " + str(e))
            raise e from None
        return {}
