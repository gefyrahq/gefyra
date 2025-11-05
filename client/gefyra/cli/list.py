import dataclasses
from typing import Optional
import click

from gefyra import api
from gefyra.cli import console
from gefyra.cli.utils import standard_error_handler
from tabulate import tabulate


@click.command("status", help="List running containers")
@click.option(
    "-n",
    "--connection-name",
    help="Only list from this client connection name.",
    type=str,
)
@standard_error_handler
def list(
    connection_name: Optional[str] = None,
):
    _containers = api.list_containers(connection_name)
    container_print = []
    for connection in _containers:
        if connection[1]:
            for container in connection[1]:
                container_print.append(
                    {
                        "connection": connection[0],
                        **dataclasses.asdict(container),
                    }.values()
                )

    if container_print:
        click.echo(
            tabulate(
                container_print,
                headers=["CONNECTION", "CONTAINER NAME", "ADDRESS", "NAMESPACE"],
                tablefmt="plain",
            )
        )
    else:
        console.info("No local containers running with Gefyra")
