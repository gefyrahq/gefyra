import logging
from pathlib import Path
from typing import Iterable, List, Optional
import uuid
from gefyra.configuration import ClientConfiguration
from gefyra.local.clients import (
    get_gefyraclient_body,
    handle_create_gefyraclient,
    handle_delete_gefyraclient,
    handle_get_gefyraclient,
)
from gefyra.types import GefyraClient
from .utils import stopwatch

logger = logging.getLogger(__name__)


@stopwatch
def add_clients(
    client_id: str,
    quantity: int = 1,
    kubeconfig: Optional[Path] = None,
    kubecontext: Optional[str] = None,
) -> Iterable[GefyraClient]:
    """
    Add a new client to the connection provider
    """
    config = ClientConfiguration(
        kube_config_file=kubeconfig, kube_context=kubecontext, ignore_connection=True
    )
    if quantity > 1 and client_id:
        raise RuntimeError("Cannot specify both quantity > 1 and client_id")
    result: List[GefyraClient] = []
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
    kubeconfig: Optional[Path] = None,
    kubecontext: Optional[str] = None,
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
    kubeconfig: Optional[Path] = None,
    kubecontext: Optional[str] = None,
    connection_name: Optional[str] = None,
    wait: bool = False,
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
    return handle_delete_gefyraclient(config, client_id, force, wait=wait)


@stopwatch
def write_client_file(
    client_id: str,
    host: Optional[str] = None,
    port: Optional[str] = None,
    kube_api: Optional[str] = None,
    kubeconfig: Optional[Path] = None,
    kubecontext: Optional[str] = None,
) -> str:
    """
    Write a client file
    """
    config = ClientConfiguration(kube_config_file=kubeconfig, kube_context=kubecontext)
    client = get_client(
        client_id, kubeconfig=config.KUBE_CONFIG_FILE, kubecontext=config.KUBE_CONTEXT
    )
    if not port:
        port = "31820"
    if host:
        gefyra_server = f"{host}:{port}"
    else:
        gefyra_server = config.get_stowaway_host(port)
    logger.debug(f"gefyra_server: {gefyra_server}")
    return client.get_client_config(
        gefyra_server=gefyra_server, k8s_server=kube_api
    ).json


@stopwatch
def list_client(
    kubeconfig: Optional[Path] = None, kubecontext: Optional[str] = None
) -> List[GefyraClient]:
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
