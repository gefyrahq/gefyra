import dataclasses
from typing import Optional
import click

from gefyra import api
from gefyra.cli import console
from gefyra.cli.utils import standard_error_handler
from tabulate import tabulate


@click.command("status", help="List running containers and bridges")
@click.option(
    "-n",
    "--connection-name",
    help="Only list from this client connection name.",
    type=str,
)
@click.option(
    "-C",
    "--containers",
    help="Only list running containers.",
    type=bool,
    is_flag=True,
)
@click.option(
    "-B",
    "--bridges",
    help="Only list running bridges.",
    type=bool,
    is_flag=True,
)
@standard_error_handler
def list(
    connection_name: Optional[str] = None,
    containers: Optional[bool] = False,
    bridges: Optional[bool] = False,
):
    show_containers = True if containers is False and bridges is False else containers
    show_bridges = True if containers is False and bridges is False else bridges
    if show_containers:
        _containers = api.list_containers(connection_name)
        container_print = []
        for connection in _containers:
            for container in connection[1]:
                container_print.append(
                    {
                        "connection": connection[0],
                        **dataclasses.asdict(container),
                    }.values()
                )

        if container_print:
            if show_bridges:
                console.heading("Gefyra Containers:")
            click.echo(
                tabulate(
                    container_print,
                    headers=["CONNECTION", "CONTAINER NAME", "ADDRESS", "NAMESPACE"],
                    tablefmt="plain",
                )
            )
            if show_bridges:
                print()

        else:
            console.info("No local Gefyra containers found")

    if show_bridges:
        bridges_print = []
        _bridges = api.list_gefyra_bridges(connection_name)
        for connection in _bridges:
            for bridge in connection[1]:
                bridges_print.append(
                    {"connection": connection[0], **dataclasses.asdict(bridge)}.values()
                )

        if bridges_print:
            if show_containers:
                console.heading("Gefyra Bridges:")
            click.echo(
                tabulate(
                    bridges_print,
                    headers=[
                        "CONNECTION",
                        "NAME",
                        "NAMESPACE",
                        "LOCAL ADDRESS",
                        "PORTS",
                        "TARGET CONTAINER",
                        "NAMESPACE",
                        "TARGET POD",
                        "PROVIDER",
                        "STATE",
                    ],
                    tablefmt="plain",
                )
            )
        else:
            console.info("No Gefyra bridges found")
