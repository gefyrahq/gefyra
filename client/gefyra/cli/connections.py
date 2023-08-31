import dataclasses
import logging
from typing import Optional

import click
from gefyra import api

from gefyra.cli.utils import AliasedGroup, standard_error_handler
from gefyra.cli import console
from tabulate import tabulate

logger = logging.getLogger(__name__)


@click.group(
    "connections",
    cls=AliasedGroup,
    help="Manage connections to clusters for this Gefyra installation",
)
@click.pass_context
def connections(ctx):
    pass


@connections.command(
    "connect",
    help="Connect this local machine to a Gefyra cluster",
)
@click.option("-f", "--client-config", type=click.File("r"))
@click.option(
    "-n",
    "--connection-name",
    help="Assign a local name to this client connection",
    type=str,
)
@click.option(
    "--minikube",
    help="Connect Gefyra to a Minikube cluster (accepts minikube profile name, default is 'minikube'))",
    type=str,
    is_flag=False,
    flag_value="minikube",  # if --minikube is used as flag, we default to profile 'minikube'
    required=False,
)
@standard_error_handler
def connect_client(client_config, connection_name: str, minikube: Optional[str] = None):
    api.connect(
        connection_name=connection_name,
        client_config=client_config,
        minikube_profile=minikube,
    )


@connections.command(
    "disconnect",
    help="Disconnect this local machine from a Gefyra cluster",
)
@click.argument("connection_name", type=str)
@standard_error_handler
def disconnect_client(connection_name):
    api.disconnect(connection_name=connection_name)


@connections.command(
    "list",
    alias=["ls"],
    help="List all Gefyra connections",
)
@standard_error_handler
def list_connections():
    conns = api.list_connections()
    data = [dataclasses.asdict(conn).values() for conn in conns]
    if data:
        click.echo(
            tabulate(
                data, headers=["NAME", "VERSION", "CREATED", "STATUS"], tablefmt="plain"
            )
        )
    else:
        console.info("No Gefyra connection found")


@connections.command(
    "remove",
    alias=["rm"],
    help="Remove a Gefyra connection",
)
@click.argument("connection_name", type=str)
@standard_error_handler
def remove_connection(connection_name):
    api.remove_connection(connection_name=connection_name)
