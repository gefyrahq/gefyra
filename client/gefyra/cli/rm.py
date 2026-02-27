import click
from gefyra.cli import console
from gefyra.cli.utils import (
    check_connection_name,
    standard_error_handler,
)


@click.command("rm", help="Remove a Gefyra container and its associated bridges")
@click.argument("name", required=False)
@click.option(
    "-A",
    "--all",
    help="Remove all Gefyra containers and their bridges",
    required=False,
    is_flag=True,
    default=False,
)
@click.option(
    "-f",
    "--force",
    help="Force remove containers (even if running)",
    required=False,
    is_flag=True,
    default=False,
)
@click.option(
    "--nowait",
    help="Do not wait for containers and bridges to be fully removed",
    required=False,
    is_flag=True,
    default=False,
)
@click.option(
    "--connection-name", type=str, default="default", callback=check_connection_name
)
@standard_error_handler
def rm(name: str, all: bool, force: bool, nowait: bool, connection_name: str):
    from gefyra import api

    if not all and not name:
        raise click.UsageError(
            "Provide a container name or use --all flag to remove all."
        )

    wait = not nowait
    if all:
        api.rm_all(connection_name=connection_name, wait=wait, force=force)
        console.success("All Gefyra containers and their bridges have been removed.")
    else:
        api.rm(name=name, connection_name=connection_name, wait=wait, force=force)
        console.success(f"Container '{name}' and its bridges have been removed.")
