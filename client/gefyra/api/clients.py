from dataclasses import dataclass
from pathlib import Path
from gefyra.configuration import default_configuration
from gefyra.local.clients import (
    get_gefyraclient_body,
    handle_create_gefyraclient,
    handle_delete_gefyraclient,
    handle_get_gefyraclient,
)
from gefyra.types import GefyraClient
from .utils import stopwatch


@stopwatch
def add_client(client_id: str, config=default_configuration) -> GefyraClient:
    """
    Add a new client to the connection provider
    """
    gclient_req = get_gefyraclient_body(config, client_id)
    gclient = handle_create_gefyraclient(config, gclient_req)
    return GefyraClient(gclient, config)


@stopwatch
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


def write_client_file(path: Path):
    """
    Write a client file
    """
    pass