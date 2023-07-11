import click
from gefyra import api
from gefyra.cli import console
from gefyra.cli.utils import check_connection_name


@click.command("bridge", help="Establish a Gefyra bridge to a container in the cluster")
@click.option(
    "-N", "--name", help="The name of the container running in Gefyra", required=True
)
@click.option(
    "-p",
    "--ports",
    # help=port_mapping_help_text,
    required=True,
    # action=PortMappingParser,
)
@click.option(
    "-n",
    "--namespace",
    #   help=namespace_help_text,
    default="default",
)
@click.option(
    "-P",
    "--no-probe-handling",
    is_flag=True,
    help="Make Carrier to not handle probes during switch operation",
    default=False,
)
@click.option(
    "--target",
    help=(
        "Intercept the container given in the notation 'resource/name/container'. "
        "Resource can be one of 'deployment', 'statefulset' or 'pod'. "
        "E.g.: --target deployment/hello-nginx/nginx"
    ),
    required=True,
)
@click.option("--connection-name", type=str, callback=check_connection_name)
def create_bridge(name, ports, target, namespace, no_probe_handling, connection_name):
    api.bridge(
        name=name,
        ports=ports,
        target=target,
        namespace=namespace,
        handle_probes=no_probe_handling,
        timeout=10,
        connection_name=connection_name,
    )


@click.command("unbridge", help="Remove a Gefyra bridge")
@click.option(
    "-N", "--name", help="The name of the container running in Gefyra", required=False
)
@click.option(
    "-A",
    "--all",
    help="Unbridge all bridges",
    required=False,
    is_flag=True,
    default=False,
)
@click.option("--connection-name", type=str, callback=check_connection_name)
def unbridge(name: str, connection_name: str, all: bool = False):
    if not all and not name:
        console.error("Provide a name or use --all flag to unbridge.")
    if all:
        api.unbridge_all(connection_name=connection_name, wait=True)
    else:
        api.unbridge(connection_name=connection_name, name=name, wait=True)
