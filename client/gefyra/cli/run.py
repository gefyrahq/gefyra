import click

from gefyra import api

from gefyra.cli.__main__ import run
from gefyra.cli.utils import standard_error_handler


@run.command("create", help="Create a new Gefyra client")
@click.option("--client-id", help="The client id", type=str)
@click.option(
    "-n",
    "quantity",
    help="Number of clients to be generated (not allowed with explicit client-id)",
    type=int,
    default=1,
)
@click.pass_context
@standard_error_handler
def create_clients(ctx, client_id, quantity):
    api.add_clients(client_id, quantity, ctx.obj["config"])
    console.success(f"{quantity} client(s) created successfully")
