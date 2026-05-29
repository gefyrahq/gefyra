import logging
import time
from typing import Optional, Union

from gefyra.configuration import ClientConfiguration
from gefyra.exceptions import GefyraBridgeMountNotFound

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
            raise RuntimeError(
                f"GefyraBridgeMount '{body['metadata']['name']}' already exists"
            )
        elif e.status == 500:
            import json

            raise RuntimeError(str(json.loads(e.body).get("message")))
        logger.error(
            f"A Kubernetes API Error occured. \nReason: {e.reason} \nBody: {e.body}"
        )
        raise e from None
    return mount


def handle_delete_gefyramount(
    config: ClientConfiguration,
    name: str,
    force: bool,
    wait: bool,
    timeout: Optional[int] = None,
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
            if not timeout:
                timeout = 60
            counter = 0
            while counter < timeout:
                try:
                    result = get_gefyrabridgemount(config=config, name=name)
                    # return early if object is not available anymore
                    if not result:
                        return True
                except (ApiException, GefyraBridgeMountNotFound):
                    return True
                time.sleep(1)
                counter += 1
            raise TimeoutError
        return True
    except ApiException as e:
        logger.debug(e)
        if e.status == 403:
            raise RuntimeError(
                "Permission denied: You don't have permission to delete this mount."
            )
        if e.status == 404:
            raise GefyraBridgeMountNotFound(
                f"GefyraBridgeMount with name '{name}' not found."
            )
        else:
            logger.error(
                f"A Kubernetes API Error occured. \nReason:{e.reason} \nBody:{e.body}"
            )
            raise e


def get_ports_from_tls_args(
    tls_certificate: Optional[list[str]] = None,
    tls_key: Optional[list[str]] = None,
    tls_sni: Optional[list[str]] = None,
) -> dict[int, dict[str, dict[str, str]]]:
    """Receives a list of TLS arguments and returns a list of ports that should be used for the mount.
    strings may contain @port to specify the port for which the TLS configuration should be applied.
    If no port is specified, the TLS configuration will be applied to all ports.

    Returns a dict with port as key and TLS configuration as value:
    {
        443: {
            "tls": {
                "certificate": tls_certificate
                "key": tls_key,
                "sni": tls_sni,
            }
        }
    }

    Or a dict with a global tls config:
    "tls": {
        "certificate": tls_certificate,
        "key": tls_key,
    }
    """
    ports: dict[int, dict[str, dict[str, str]]] = {}

    def parse_arg(arg: str) -> tuple[str, Optional[int]]:
        """Parse an argument that may contain @port suffix."""
        if "@" in arg:
            value, port_str = arg.rsplit("@", 1)
            try:
                return value, int(port_str)
            except ValueError:
                raise ValueError(f"Invalid port specification: {port_str}")
        return arg, None

    # Process certificates
    if tls_certificate:
        for cert in tls_certificate:
            value, port = parse_arg(cert)
            if port is not None:
                if port not in ports:
                    ports[port] = {"tls": {}}
                ports[port]["tls"]["certificate"] = value

    # Process keys
    if tls_key:
        for key in tls_key:
            value, port = parse_arg(key)
            if port is not None:
                if port not in ports:
                    ports[port] = {"tls": {}}
                ports[port]["tls"]["key"] = value

    # Process SNI
    if tls_sni:
        for sni in tls_sni:
            value, port = parse_arg(sni)
            if port is not None:
                if port not in ports:
                    ports[port] = {"tls": {}}
                ports[port]["tls"]["sni"] = value

    for port, config in ports.items():
        if "certificate" not in config["tls"] or "key" not in config["tls"]:
            raise ValueError(
                f"TLS configuration for port {port} requires both certificate and key."
            )

    return ports


# Type alias for TLS configuration
TlsConfigGlobal = dict[str, dict[str, Union[list[str], str]]]
TlsConfigPerPort = dict[int, dict[str, dict[str, str]]]


def get_tls_config(
    tls_certificate: Optional[list[str]] = None,
    tls_key: Optional[list[str]] = None,
    tls_sni: Optional[list[str]] = None,
) -> TlsConfigGlobal | TlsConfigPerPort:
    ports = get_ports_from_tls_args(tls_certificate, tls_key, tls_sni)

    if len(ports) == 0:
        if not tls_certificate and not tls_key:
            return {}
        if not tls_certificate or not tls_key:
            raise RuntimeError(
                "TLS configuration requires both certificate and key to be set."
            )
        res: TlsConfigGlobal = {
            "tls": {
                "certificate": tls_certificate,
                "key": tls_key,
            }
        }
        if tls_sni is not None:
            res["tls"]["sni"] = tls_sni
        return res
    else:
        return ports


def get_gbridgemount_body(
    config: ClientConfiguration,
    name: str,
    target: str,
    provider: str,
    target_namespace: str,
    target_container: str,
    tls_certificate: Optional[list[str]] = None,
    tls_key: Optional[list[str]] = None,
    tls_sni: Optional[list[str]] = None,
) -> dict[str, str | dict[str, str] | TlsConfigGlobal | TlsConfigPerPort]:
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
        "provider": provider,
        "providerParameter": get_tls_config(
            tls_certificate=tls_certificate,
            tls_key=tls_key,
            tls_sni=tls_sni,
        ),
    }


def get_gefyrabridgemount(config: ClientConfiguration, name: str):
    from kubernetes.client import ApiException

    try:
        mount = config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object(
            name=name,
            namespace=config.NAMESPACE,
            group="gefyra.dev",
            plural="gefyrabridgemounts",
            version="v1",
        )
        return mount
    except ApiException as e:
        if e.status == 404:
            raise GefyraBridgeMountNotFound(
                f"GefyraBridgeMount with name '{name}' not found."
            )
        else:
            logger.warning("Error getting GefyraBridgeMounts: " + str(e))
            raise e from None
