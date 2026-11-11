import logging
import uuid
from collections.abc import Iterable
from pathlib import Path

from gefyra.configuration import ClientConfiguration
from gefyra.exceptions import CommandTimeoutError
from gefyra.local.clients import (
    get_gefyraclient_body,
    handle_create_gefyraclient,
    handle_delete_gefyraclient,
    handle_get_gefyraclient,
)
from gefyra.types import LOCAL_SERVER, GefyraClient

from .utils import stopwatch

logger = logging.getLogger(__name__)


@stopwatch
def add_clients(
    client_id: str,
    quantity: int = 1,
    registry: str | None = None,
    kubeconfig: Path | None = None,
    kubecontext: str | None = None,
) -> Iterable[GefyraClient]:
    """
    Add a new client to the connection provider
    """
    config = ClientConfiguration(
        kube_config_file=kubeconfig,
        kube_context=kubecontext,
        ignore_connection=True,
        registry=registry,
    )
    if quantity > 1 and client_id:
        raise RuntimeError("Cannot specify both quantity > 1 and client_id")
    result: list[GefyraClient] = []
    while len(result) < quantity:
        if not bool(client_id):
            generated_uuid = uuid.uuid4()
            client_id = str(generated_uuid).replace("-", "")

        logger.info(f"Creating client with id: {client_id}")
        gclient_req = get_gefyraclient_body(config, client_id)
        gclient = handle_create_gefyraclient(config, gclient_req)
        result.append(GefyraClient(gclient, config))
        client_id = ""
    return result


@stopwatch
def get_client(
    client_id: str,
    connection_name: str = "",
    kubeconfig: Path | None = None,
    kubecontext: str | None = None,
) -> GefyraClient:
    """
    Get a GefyraClient object
    """
    config_params = {"connection_name": connection_name}
    if kubeconfig:
        config_params.update({"kube_config_file": str(kubeconfig)})

    if kubecontext:
        config_params.update({"kube_context": kubecontext})
    config = ClientConfiguration(**config_params)  # type: ignore
    gclient = handle_get_gefyraclient(config, client_id)
    return GefyraClient(gclient, config)


@stopwatch
def delete_client(
    client_id: str,
    force: bool = False,
    kubeconfig: Path | None = None,
    kubecontext: str | None = None,
    connection_name: str | None = None,
    wait: bool = False,
    timeout: int | None = None,
) -> bool:
    """
    Delete a GefyraClient configuration
    """
    config = ClientConfiguration(
        kube_config_file=kubeconfig,
        kube_context=kubecontext,
        connection_name=connection_name if connection_name else "no-connection-name",
        # use no-connection-name to make sure you use admin access to the cluster
    )
    try:
        return handle_delete_gefyraclient(
            config, client_id, force, wait=wait, timeout=timeout
        )
    except TimeoutError:
        raise CommandTimeoutError("Timeout for deleting GefyraClient exceeded")


@stopwatch
def write_client_file(
    client_id: str,
    host: str | None = None,
    port: str | None = None,
    kube_api: str | None = None,
    kubeconfig: Path | None = None,
    kubecontext: str | None = None,
    registry: str | None = None,
    wireguard_mtu: int | None = None,
    local: bool = False,
) -> str:
    """
    Write a client file
    """
    config = ClientConfiguration(
        kube_config_file=kubeconfig,
        kube_context=kubecontext,
        registry=registry,
        wireguard_mtu=str(wireguard_mtu) if wireguard_mtu else None,
    )
    client = get_client(
        client_id, kubeconfig=config.KUBE_CONFIG_FILE, kubecontext=config.KUBE_CONTEXT
    )
    if not port:
        port = "31820"
    if host:
        gefyra_server = f"{host}:{port}"
    elif local:
        gefyra_server = LOCAL_SERVER
    else:
        gefyra_server = config.get_stowaway_host(port)
    logger.debug(f"gefyra_server: {gefyra_server}")
    return client.get_client_config(
        gefyra_server=gefyra_server,
        k8s_server=kube_api,
        registry=registry,
        wireguard_mtu=wireguard_mtu,
    ).json


@stopwatch
def list_client(
    kubeconfig: Path | None = None, kubecontext: str | None = None
) -> list[GefyraClient]:
    """
    List all GefyraClient objects
    """
    config = ClientConfiguration(kube_config_file=kubeconfig, kube_context=kubecontext)
    clients = config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object(
        namespace=config.NAMESPACE,
        group="gefyra.dev",
        plural="gefyraclients",
        version="v1",
    )
    return [GefyraClient(client, config) for client in clients["items"]]
