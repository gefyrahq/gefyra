from argparse import Namespace
from dataclasses import dataclass
import logging
from typing import Iterable, List, Optional
import uuid

from pathlib import Path
from gefyra.configuration import default_configuration
from gefyra.local.clients import (
    get_gefyraclient_body,
    handle_create_gefyraclient,
    handle_delete_gefyraclient,
    handle_get_gefyraclient,
)
from gefyra.types import GefyraClient
from tabulate import tabulate
from .utils import stopwatch

logger = logging.getLogger(__name__)


@stopwatch
def add_clients(
    client_id: str, quantity: int = 1, config=default_configuration
) -> Iterable[GefyraClient]:
    """
    Add a new client to the connection provider
    """
    if quantity > 1 and client_id:
        raise RuntimeError("Cannot specify both quantity > 1 and client_id")
    result = []
    while len(result) < quantity:
        if not client_id:
            generated_uuid = uuid.uuid4()
            client_id = str(generated_uuid).replace("-", "")

        logger.info(f"Creating client with id: {client_id}")
        gclient_req = get_gefyraclient_body(config, client_id)
        gclient = handle_create_gefyraclient(config, gclient_req)
        result.append(GefyraClient(gclient, config))
        client_id = None
    return result


def get_client(client_id: str, config=default_configuration) -> GefyraClient:
    """
    Get a GefyraClient object
    """
    gclient = handle_get_gefyraclient(config, client_id)
    return GefyraClient(gclient, config)


@stopwatch
def delete_client(client_id: str, config=default_configuration) -> None:
    """
    Delete a GefyraClient configuration
    """
    handle_delete_gefyraclient(config, client_id)


@stopwatch
def write_client_file(
    client_id: str, path: Path, host: str = None, port: str = None, kube_api: str = None
):
    """
    Write a client file
    """
    client = get_client(client_id)
    gefyra_server = None
    if not port:
        port = "51820"
    if host:
        gefyra_server = f"{host}:{port}"

    json_str = client.get_client_config(
        gefyra_server=gefyra_server, k8s_server=kube_api
    ).json

    if not path:
        print(json_str)
    else:
        with open(path, "w") as f:
            f.write(json_str)
    return True


@stopwatch
def list_client(config=default_configuration) -> List[GefyraClient]:
    """
    List all GefyraClient objects
    """
    clients = config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object(
        namespace=config.NAMESPACE,
        group="gefyra.dev",
        plural="gefyraclients",
        version="v1",
    )
    return [GefyraClient(client, config) for client in clients["items"]]
    # Todo move to CLI
    # clients = [
    #     [
    #         client["metadata"]["name"],
    #         client["state"],
    #         client["stateTransitions"]["CREATING"],
    #     ]
    #     for client in clients["items"]
    # ]
    # print(tabulate(clients, headers=["ID", "STATE", "CREATED"], tablefmt="plain"))


def client(args: Namespace, config=default_configuration):
    """
    Run a client command
    """
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
