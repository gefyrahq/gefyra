from argparse import Namespace
import logging
from typing import Iterable, List
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
) -> Iterable[GefyraClient]:
    """
    Add a new client to the connection provider
    """
    config = ClientConfiguration()
    if quantity > 1 and client_id:
        raise RuntimeError("Cannot specify both quantity > 1 and client_id")
    result: List[GefyraClient] = []
    while len(result) < quantity:
        if not client_id:
            generated_uuid = uuid.uuid4()
            client_id = str(generated_uuid).replace("-", "")

        logger.info(f"Creating client with id: {client_id}")
        gclient_req = get_gefyraclient_body(config, client_id)
        gclient = handle_create_gefyraclient(config, gclient_req)
        result.append(GefyraClient(gclient))
    return result


def get_client(client_id: str, connection_name: str = "") -> GefyraClient:
    """
    Get a GefyraClient object
    """
    config = ClientConfiguration(connection_name=connection_name)
    gclient = handle_get_gefyraclient(config, client_id)
    return GefyraClient(gclient)


@stopwatch
def delete_client(client_id: str, force: bool = False) -> bool:
    """
    Delete a GefyraClient configuration
    """
    config = ClientConfiguration()
    return handle_delete_gefyraclient(config, client_id, force)


@stopwatch
def write_client_file(
    client_id: str, host: str, port: str = "", kube_api: str = ""
) -> str:
    """
    Write a client file
    """
    client = get_client(client_id)
    if not port:
        port = "31820"
    if host:
        gefyra_server = f"{host}:{port}"

    json_str = client.get_client_config(
        gefyra_server=gefyra_server, k8s_server=kube_api
    ).json
    return json_str


@stopwatch
def list_client() -> List[GefyraClient]:
    """
    List all GefyraClient objects
    """
    config = ClientConfiguration()
    clients = config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object(
        namespace=config.NAMESPACE,
        group="gefyra.dev",
        plural="gefyraclients",
        version="v1",
    )
    return [GefyraClient(client) for client in clients["items"]]


# TODO becomes obsolete
def client(args: Namespace):
    """
    Run a client command
    """
    config = ClientConfiguration()
    if args.verb == "create":
        add_clients(
            getattr(args, "client_id", None), getattr(args, "quantity", 1), config
        )
    if args.verb == "delete":
        delete_client(args.client_id, config)
    if args.verb == "list":
        list_client(config)
    if args.verb == "config":
        write_client_file(
            args.client_id,
            args.path,
            host=args.host,
            port=args.port,
            kube_api=args.kube_api,
        )
