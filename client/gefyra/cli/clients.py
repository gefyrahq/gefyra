import click
from gefyra import api
from gefyra.cli.__main__ import clients
from gefyra.cli import console
from gefyra.cli.utils import standard_error_handler
from tabulate import tabulate


@clients.command("create", help="Create a new Gefyra client")
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


@clients.command(
    "delete", alias=["rm", "remove"], help="Mark a Gefyra client for deletion"
)
@click.argument("client_id", nargs=-1, required=True)
@click.pass_context
@standard_error_handler
def delete_client(ctx, client_id):
    for _del in list(client_id):
        deleted = api.delete_client(_del, ctx.obj["config"])
        if deleted:
            console.success(f"Client {_del} deleted successfully")


@clients.command("list", alias=["ls"], help="List all Gefyra clients")
@click.pass_context
@standard_error_handler
def list_client(ctx):
    gefyraclients = api.list_client(ctx.obj["config"])
    clients = [
        [
            c.client_id,
            c.state,
            c.state_transitions.get("CREATING", "Creating..."),
        ]
        for c in gefyraclients
    ]
    click.echo(tabulate(clients, headers=["ID", "STATE", "CREATED"], tablefmt="plain"))


@clients.command("inspect", alias=["show", "get"], help="Discribe a Gefyra client")
@click.argument("client_id")
@click.pass_context
def inspect_client(ctx, client_id):
    client = api.get_client(client_id, ctx.obj["config"])
    console.heading(client.client_id)
    console.info(f"uid: {client.uid}")
    console.info(f"States: {client.state_transitions}")
