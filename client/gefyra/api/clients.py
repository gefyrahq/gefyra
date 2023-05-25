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


def write_client_file(client_id: str, path: Path, config=default_configuration):
    """
    Write a client file
    """
    client = get_client(client_id)
    json_str = client.get_client_config("me").json
    if not path:
        print(json_str)
    else:
        with open(path, "w") as f:
            f.write(json_str)
    return True


def client(args: Namespace, config=default_configuration):
    """
    Run a client command
    """
    if args.verb == "create":
        add_client(getattr(args, "client_id", None), config)
    if args.verb == "delete":
        delete_client(args.client_id, config)
    if args.verb == "list":
        pass
    if args.verb == "config":
        write_client_file(args.client_id, args.path, config=config)
