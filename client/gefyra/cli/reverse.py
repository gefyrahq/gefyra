import click
from gefyra.api.reverse import _patch_workload, create_reverse_service
from gefyra.cli.utils import parse_ip_port_map, standard_error_handler


@click.command("reverse", help="Create reverse service.")
@click.option(
    "-n",
    "--name",
    help="",
    type=str,
)
@click.option(
    "-l",
    "--network",
    help="",
    type=str,
)
@click.option(
    "-p",
    "--ports",
    help="Add forward port mapping in form of <remote_container_port>:<local_container_port>",
    required=True,
    multiple=True,
    callback=parse_ip_port_map,
)
@click.option(
    "-c",
    "--client-id",
    help="Your client id",
    type=str,
)
@click.option(
    "-d",
    "--deployment-name",
    help="Target deployment",
    type=str,
)
@click.option(
    "-k",
    "--namespace",
    help="Target namespace",
    type=str,
)
@click.option(
    "-p",
    "--container-name",
    help="Target container in deployment",
    type=str,
)
@standard_error_handler
def reverse(
    name: str,
    ports: dict,
    client_id: str,
    network: str,
    deployment_name: str,
    namespace: str,
    container_name: str,
):
    create_reverse_service(name, ports, client_id, network)
    _patch_workload(
        deployment_name,
        namespace,
        container_name,
    )
