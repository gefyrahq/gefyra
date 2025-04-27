import click
from gefyra.api.duplicate import duplicate_deployment, duplicate_service
from gefyra.cli.utils import check_connection_name, standard_error_handler


@click.command("duplicate", help="Duplicate a deployment.")
@click.option(
    "-d",
    "--deployment-name",
    help="",
    type=str,
)
@click.option(
    "-s",
    "--service-name",
    help="",
    type=str,
)
@click.option(
    "-n",
    "--namespace",
    help="Namespace of the deployment.",
    type=str,
)
@click.option(
    "--connection-name", type=str, callback=check_connection_name, required=False
)
@standard_error_handler
def duplicate(
    deployment_name: str, service_name: str, namespace: str, connection_name: str
):
    duplicate_deployment(connection_name, deployment_name, namespace)
    duplicate_service(connection_name, service_name, namespace)
