import dataclasses
import logging
from typing import Optional
import click

from gefyra.cli.utils import AliasedGroup, check_connection_name, standard_error_handler
from gefyra.cli import console
from tabulate import tabulate

logger = logging.getLogger(__name__)


def _manage_container_and_bridges(connection_name: str, force: bool = False):
    import kubernetes
    import urllib3
    from gefyra import api
    from gefyra.configuration import ClientConfiguration

    try:
        _bridges = api.list_gefyra_bridges(connection_name)
        if _bridges and len(_bridges[0][1]) > 0:
            console.info(
                f"There is {len(_bridges[0][1])} Gefyra bridge(s) running with connection '{connection_name}'."
            )
            if force:
                _del = True
            elif click.confirm("Do you want to remove them?", abort=True):
                _del = True
            if _del:
                for gbridges in _bridges[0][1]:
                    api.unbridge(
                        name=gbridges.name,
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
                container = ClientConfiguration(
                    connection_name=connection_name
                ).DOCKER.containers.get(gcontainers.name)
                container.remove(force=True)


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
@standard_error_handler
def connect_client(client_config, connection_name: str, minikube: Optional[str] = None):
    from alive_progress import alive_bar
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
    ):
        api.connect(
            connection_name=connection_name,
            client_config=client_config,
            minikube_profile=minikube,
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
@click.argument(
    "connection_name", type=str, default="default", callback=check_connection_name
)
@standard_error_handler
def disconnect_client(connection_name: str):
    from gefyra import api

    _manage_container_and_bridges(connection_name=connection_name)
    api.disconnect(connection_name=connection_name)


@connections.command(
    "list",
    alias=["ls"],
    help="List all Gefyra connections",
)
@standard_error_handler
def list_connections():
    from gefyra import api

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
@click.argument(
    "connection_name", type=str, default="default", callback=check_connection_name
)
# @standard_error_handler
def remove_connection(connection_name: str):
    from gefyra import api

    _manage_container_and_bridges(connection_name=connection_name)
    api.remove_connection(connection_name=connection_name)
