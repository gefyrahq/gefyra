import logging

import click
from gefyra import api
from gefyra.api.clients import get_client

from gefyra.cli.utils import standard_error_handler
from gefyra.cli.__main__ import connections
from tabulate import tabulate

logger = logging.getLogger(__name__)


@connections.command(
    "connect",
    help="Connect this local machine to a Gefyra cluster",
)
@click.argument("client_config", type=click.File("r"))
@click.option(
    "-n",
    "--connection-name",
    help="Assign a local name to this client connection",
    type=str,
)
# @standard_error_handler
def connect_client(client_config, connection_name: str):
    api.connect(client=client_config, connection_name=connection_name)


@connections.command(
    "disconnect",
    help="Disconnect this local machine from a Gefyra cluster",
)
@click.argument("connection_name", type=str)
@click.pass_context
@standard_error_handler
def disconnect_client(ctx, connection_name):
    api.disconnect(get_client(config.CLIENT_ID, connection_name=connection_name))


@connections.command(
    "list",
    alias=["ls"],
    help="List all Gefyra connections",
)
@click.pass_context
def list_connections(ctx):
    conns = api.list_connections(ctx.obj["config"])
    data = [conn.values() for conn in conns]
    click.echo(
        tabulate(
            data, headers=["NAME", "VERSION", "CREATED", "STATUS"], tablefmt="plain"
        )
    )
