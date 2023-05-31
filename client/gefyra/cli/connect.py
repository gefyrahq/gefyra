import logging
import os

import click
from gefyra.configuration import get_gefyra_config_location
from gefyra.local.utils import compose_kubeconfig_for_serviceaccount

from gefyra.types import GefyraClientConfig

from gefyra.cli import console
from gefyra.cli.utils import standard_error_handler
from gefyra.cli.__main__ import cli as _cli

logger = logging.getLogger(__name__)


@_cli.command(
    "connect",
    help="Connect this local machine to a Gefyra cluster",
)
@click.argument("client_config", type=click.File("r"))
@click.option("-n", "--name", help="Name of the client connection", type=str)
@click.pass_context
@standard_error_handler
def connect_client(ctx, client_config, name):
    import hashlib

    file_str = client_config.read()
    # TODO migrate to a utils function to make it available for gefyra-ext too?
    # copy & transform client config to kubeconfig
    config_name = name or hashlib.md5(file_str.encode("utf-8")).hexdigest()
    gclient_conf = GefyraClientConfig.from_json_str(file_str)
    loc = os.path.join(
        get_gefyra_config_location(ctx.obj["config"]), f"{config_name}.yaml"
    )
    kubeconfig_str = compose_kubeconfig_for_serviceaccount(
        gclient_conf.kubernetes_server,
        gclient_conf.ca_crt,
        "default",
        gclient_conf.token,
    )
    with open(loc, "w") as f:
        f.write(kubeconfig_str)
        console.info(f"Client kubeconfig saved to {loc}")

    # TODO this is just for testing
    ctx.obj["config"].KUBE_CONFIG_FILE = loc
    clients = ctx.obj["config"].K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object(
        namespace=ctx.obj["config"].NAMESPACE,
        group="gefyra.dev",
        plural="gefyraclients",
        version="v1",
    )

    click.echo(clients["items"])
