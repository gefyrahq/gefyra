import os
import click
from gefyra.cli import console
from gefyra.cli.utils import AliasedGroup, standard_error_handler
from tabulate import tabulate


@click.group(
    "clients", cls=AliasedGroup, help="Manage clients for a Gefyra installation"
)
@click.pass_context
def clients(ctx):
    # for management of clients we always sourcing the kubeconfig and context from env if not passed
    if ctx.obj["kubeconfig"] is None:
        ctx.obj["kubeconfig"] = os.environ.get("KUBECONFIG") or os.path.expanduser(
            "~/.kube/config"
        )


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
    from gefyra import api

    api.add_clients(
        client_id,
        quantity,
        kubeconfig=ctx.obj["kubeconfig"],
        kubecontext=ctx.obj["context"],
    )
    console.success(f"{quantity} client(s) created successfully")


@clients.command(
    "delete", alias=["rm", "remove"], help="Mark a Gefyra client for deletion"
)
@click.argument("client_id", nargs=-1, required=True)
@click.pass_context
@standard_error_handler
def delete_client(ctx, client_id):
    from gefyra import api

    for _del in list(client_id):
        deleted = api.delete_client(
            _del, kubeconfig=ctx.obj["kubeconfig"], kubecontext=ctx.obj["context"]
        )
        if deleted:
            console.success(f"Client {_del} marked for deletion")


@clients.command("list", alias=["ls"], help="List all Gefyra clients")
@click.pass_context
@standard_error_handler
def list_client(ctx):
    from gefyra import api

    gefyraclients = api.list_client(
        kubeconfig=ctx.obj["kubeconfig"], kubecontext=ctx.obj["context"]
    )
    clients = [
        [
            c.client_id,
            c.state,
            c.state_transitions.get("CREATING", "Creating..."),
        ]
        for c in gefyraclients
    ]
    click.echo(tabulate(clients, headers=["ID", "STATE", "CREATED"], tablefmt="plain"))


@clients.command("inspect", alias=["show", "get"], help="Describe a Gefyra client")
@click.argument("client_id")
@click.pass_context
@standard_error_handler
def inspect_client(ctx, client_id):
    from gefyra import api

    client = api.get_client(
        client_id, kubeconfig=ctx.obj["kubeconfig"], kubecontext=ctx.obj["context"]
    )
    console.heading(client.client_id)
    console.info(f"uid: {client.uid}")
    console.info(f"States: {client.state_transitions}")


@clients.command(
    "config", alias=["write"], help="Get a Gefyra connection config for a client"
)
@click.argument("client_id")
@click.option("-h", "--host", help="The connection host", type=str)
@click.option("-p", "--port", help="The connection port (default: 31820)", type=int)
@click.option(
    "-a",
    "--kube-api",
    "--kubernetes-api",
    help=(
        "The Kubernetes API adress for the host cluster (default: API adresse of your"
        " kubeconfig)"
    ),
    type=str,
)
@click.option(
    "-o",
    "--output",
    help="The output file to write the config to",
    type=click.File("wb"),
)
@click.pass_context
@standard_error_handler
def get_config(ctx, client_id, host, port, kube_api, output):
    from gefyra import api

    json_str = api.write_client_file(
        client_id,
        host=host,
        port=port,
        kube_api=kube_api,
        kubeconfig=ctx.obj["kubeconfig"],
        kubecontext=ctx.obj["context"],
    )
    if output:
        output.write(json_str.encode("utf-8"))
    else:
        click.echo(json_str)
