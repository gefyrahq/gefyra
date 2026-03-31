import json
import logging
from typing import Callable, Optional

import click
from alive_progress import alive_bar
from tabulate import tabulate

from gefyra.cli import console
from gefyra.cli.utils import AliasedGroup, check_connection_name, standard_error_handler

logger = logging.getLogger(__name__)


def _manage_container_and_bridges(
    connection_name: str,
    force: bool = False,
    update_callback: Callable[[str], None] | None = None,
):
    import kubernetes
    import urllib3

    from gefyra import api
    from gefyra.configuration import ClientConfiguration

    try:
        _bridges = api.list_bridges(connection_name=connection_name)
        if _bridges and len(_bridges) > 0:
            console.info(
                f"There is {len(_bridges)} GefyraBridge(s) running with connection '{connection_name}'."
            )
            if force:
                _del = True
            elif click.confirm("Do you want to remove them?", abort=True):
                _del = True
            if _del:
                for _container, gbridge in _bridges:
                    if update_callback:
                        update_callback(f"Removing GefyraBridge '{gbridge.name}'...")
                    api.delete_bridge(
                        name=gbridge.name,
                        connection_name=connection_name,
                    )
    except (
        urllib3.exceptions.MaxRetryError,
        kubernetes.client.exceptions.ApiException,
    ):
        logger.warning("Cannot detect it there are any Gefyra bridges running")
    _containers = api.list_containers(connection_name)
    if _containers and len(_containers[0][1]) > 0:
        console.info(
            f"There is {len(_containers[0][1])} Gefyra container(s) running with connection '{connection_name}'."
        )
        if force:
            _del = True
        elif click.confirm("Do you want to remove them?", abort=True):
            _del = True
        if _del:
            for gcontainers in _containers[0][1]:
                if update_callback:
                    update_callback(f"Removing Gefyra cargo '{gcontainers.name}'...")
                container = ClientConfiguration(
                    connection_name=connection_name
                ).DOCKER.containers.get(gcontainers.name)
                container.remove(force=True)


@click.group(
    "connections",
    cls=AliasedGroup,
    help="Manage connections to Kubernetes clusters for a GefyraClient on this machine",
)
@click.pass_context
def connections(ctx):
    pass


@connections.command(
    "connect",
    alias=["create"],
    help="Connect this local machine to a Gefyra cluster",
)
@click.option("-f", "--client-config", type=click.File("r"))
@click.option(
    "-n",
    "--connection-name",
    default="default",
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
@click.option(
    "--mtu",
    help="The MTU (Maximum Transmission Unit) for the Wireguard interface (default: auto-detected by WireGuard)",
    type=int,
    default=None,
)
@click.option(
    "--cargo-image",
    help="Use a custom Cargo container image",
    type=str,
    default=None,
)
@click.option(
    "--force",
    is_flag=True,
    help="Force re-connection of client, even if it is already active.",
)
@click.option(
    "--timeout",
    type=int,
    help="Timeout for each connection step in seconds.",
    default=60,
)
@click.pass_context
@standard_error_handler
def connect_client(
    ctx,
    client_config,
    connection_name: str,
    minikube: Optional[str] = None,
    mtu: int = None,
    cargo_image: Optional[str] = None,
    force: bool = False,
    timeout: int = 60,
):
    from gefyra import api

    conn_list = api.list_connections()
    if (
        client_config
        and conn_list
        and connection_name in [conn.name for conn in conn_list]
    ):
        raise click.BadArgumentUsage(
            message=f"The connection name '{connection_name}' already exists. Run 'gefyra connections list' to "
            "see all connections. If this is a reconnect, please omit the --client-config option."
        )
    with alive_bar(
        total=None,
        length=20,
        title=f"Creating the cluster connection '{connection_name}'",
        bar="smooth",
        spinner="classic",
        stats=False,
        dual_line=True,
    ) as bar:
        api.connect(
            connection_name=connection_name,
            kubeconfig=ctx.obj["kubeconfig"],
            kubecontext=ctx.obj["context"],
            client_config=client_config,
            minikube_profile=minikube,
            mtu=mtu,
            update_callback=bar.text,
            cargo_image=cargo_image,
            force=force,
            timeout=timeout,
        )
    console.success(
        f"Connection established with connection name '{connection_name}'. "
        "Run 'gefyra connections list' to see all connections."
    )


@connections.command(
    "disconnect",
    alias=["stop", "halt"],
    help="Disconnect this local machine from a Gefyra cluster",
)
@click.option(
    "--yes",
    help="Non-interactive mode, do not ask for confirmation",
    type=bool,
    is_flag=True,
    default=False,
)
@click.option(
    "--nowait",
    is_flag=True,
    help="Do not wait for the GefyraClient to be in state 'WAITING'",
)
@click.option(
    "--timeout",
    type=int,
    help="Timeout for disconnect in seconds.",
    default=60,
)
@click.argument("connection_name", type=str, default="default")
@standard_error_handler
def disconnect_client(
    yes: bool, connection_name: str, timeout: int, nowait: bool = False
):
    from gefyra import api

    with alive_bar(
        total=None,
        length=20,
        title=f"Disconnecting '{connection_name}'",
        bar="smooth",
        spinner="classic",
        stats=False,
        dual_line=True,
    ) as bar:
        bar.text(f"Disconnecting Gefyra connection '{connection_name}'...")
        try:
            _manage_container_and_bridges(
                connection_name=connection_name, force=yes, update_callback=bar.text
            )
        except (RuntimeError, Exception):
            bar.text(f"No local connection '{connection_name}'...")
        if not nowait:
            bar.text("Waiting for the GefyraClient to be in state 'WAITING'...")
        api.disconnect(
            connection_name=connection_name,
            nowait=nowait,
            update_callback=bar.text,
            timeout=timeout,
        )


@connections.command(
    "list",
    alias=["ls"],
    help="List all Gefyra connections",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format for the connection list",
)
@standard_error_handler
def list_connections(output: str):
    from gefyra import api

    conns = api.list_connections()
    if output == "text":
        data = [conn.list_values for conn in conns]
        if data:
            click.echo(
                tabulate(
                    data,
                    headers=["NAME", "VERSION", "CREATED", "STATUS"],
                    tablefmt="plain",
                )
            )
        else:
            console.info("No Gefyra connection found")
    elif output == "json":
        res = {}
        for conn in conns:
            res[conn.name] = conn.list_dict
        click.echo(json.dumps(res))
    else:
        raise ValueError(f"Unsupported output format: {output}")


@connections.command(
    "remove",
    alias=["rm"],
    help="Remove a Gefyra connection",
)
@click.option(
    "--yes",
    help="Non-interactive mode, do not ask for confirmation",
    type=bool,
    is_flag=True,
    default=False,
)
@click.argument(
    "connection_name", type=str, default="default", callback=check_connection_name
)
@standard_error_handler
def remove_connection(yes: bool, connection_name: str):
    from gefyra import api

    try:
        _manage_container_and_bridges(connection_name=connection_name, force=yes)
    except RuntimeError:
        pass
    api.remove_connection(connection_name=connection_name)


@connections.command(
    "inspect",
    help="Inspect a Gefyra connection",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format for the connection details",
)
@click.argument("connection_name", type=str, default="default")
@standard_error_handler
def inspect_connection(connection_name: str, output: str):
    from gefyra import api

    conn = api.inspect_connection(connection_name=connection_name)
    if output == "json":
        click.echo(conn.json)
    else:
        console.heading(conn.name)
        console.info(f"Version: {conn.version}")
        console.info(f"Created: {conn.created}")
        console.info(f"Cargo Status: {conn.status}")
        console.info(f"Gefyra Client (Cluster) Status: {conn.client_status}")
