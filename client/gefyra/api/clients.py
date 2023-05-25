from argparse import Namespace
from dataclasses import dataclass
import logging
from typing import Optional
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
from .utils import stopwatch

logger = logging.getLogger(__name__)


@dataclass
class GefyraClientFile:
    cacrt: str
    url: str
    access_token: str
    namespace: Optional[str] = None
    current_context: Optional[str] = None
    user: str
    host: str
    port: str


@stopwatch
def add_client(client_id: str, config=default_configuration) -> GefyraClient:
    """
    Add a new client to the connection provider
    """
    if not client_id:
        generated_uuid = uuid.uuid4()
        client_id = str(generated_uuid).replace("-", "")

    logger.info(f"Creating client with id: {client_id}")
    gclient_req = get_gefyraclient_body(config, client_id)
    gclient = handle_create_gefyraclient(config, gclient_req)
    return GefyraClient(gclient, config)

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


def client(args: Namespace, config=default_configuration):
    """
    Run a client command
    """
    if args.verb == "create":
        add_client(args.client_id, config)
    if args.verb == "delete":
        delete_client(args.client_id, config)
    if args.verb == "list":
        pass