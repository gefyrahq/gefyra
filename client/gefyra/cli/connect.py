import base64
import logging
import os

import click
from gefyra import api
from gefyra.api.clients import get_client
from gefyra.configuration import (
    get_configuration_for_connection_name,
    get_gefyra_config_location,
)
from gefyra.local.clients import handle_get_gefyraclient
from gefyra.local.utils import compose_kubeconfig_for_serviceaccount

from gefyra.types import GefyraClientConfig

from gefyra.cli import console
from gefyra.cli.utils import standard_error_handler
from gefyra.cli.__main__ import connections
from tabulate import tabulate

logger = logging.getLogger(__name__)


@connections.command(
    "connect",
    help="Connect this local machine to a Gefyra cluster",
)
@click.argument("client_config", type=click.File("r"))
@click.option("-n", "--connection-name", help="Assign a local name to this client connection", type=str)
@click.pass_context
# @standard_error_handler
def connect_client(ctx, client_config, connection_name):
    import hashlib

    configuration = ctx.obj["config"]
    file_str = client_config.read()
    # TODO migrate to a utils function to make it available for gefyra-ext too?
    # copy & transform client config to kubeconfig
    configuration.CONNECTION_NAME = connection_name or hashlib.md5(file_str.encode("utf-8")).hexdigest()
    gclient_conf = GefyraClientConfig.from_json_str(file_str)
    loc = os.path.join(
        get_gefyra_config_location(ctx.obj["config"]), f"{configuration.CONNECTION_NAME}.yaml"
    )
    kubeconfig_str = compose_kubeconfig_for_serviceaccount(
        gclient_conf.kubernetes_server,
        gclient_conf.ca_crt,
        "gefyra",
        base64.b64decode(gclient_conf.token).decode("utf-8"),
    )
    with open(loc, "w") as f:
        f.write(kubeconfig_str)
        console.info(f"Client kubeconfig saved to {loc}")

    configuration.KUBE_CONFIG_FILE = loc
    configuration.CLIENT_ID = gclient_conf.client_id
    configuration.CARGO_ENDPOINT = gclient_conf.gefyra_server
    api.connect(get_client(gclient_conf.client_id, configuration), configuration)


@connections.command(
    "disconnect",
    help="Disconnect this local machine from a Gefyra cluster",
)
@click.argument("connection_name", type=str)
@click.pass_context
@standard_error_handler
def disconnect_client(ctx, connection_name):
    config = get_configuration_for_connection_name(connection_name)
    api.disconnect(get_client(config.CLIENT_ID, config), config)


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
