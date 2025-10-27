import os
import pprint
from alive_progress import alive_bar
import click
from gefyra.cli import console
from gefyra.cli.utils import AliasedGroup, standard_error_handler
from gefyra.types import GefyraClient
from tabulate import tabulate


@click.group(
    "clients", cls=AliasedGroup, help="Manage GefyraClients for a Gefyra installation"
)
@click.pass_context
def clients(ctx):
    # for management of GefyraClient we always sourcing the kubeconfig and context from env if not passed
    if ctx.obj["kubeconfig"] is None:
        ctx.obj["kubeconfig"] = os.environ.get("KUBECONFIG") or os.path.expanduser(
            "~/.kube/config"
        )


@clients.command("create", help="Create a new GefyraClient")
@click.option("--client-id", help="The client id", type=str)
@click.option(
    "-n",
    "quantity",
    help="Number of GefyraClient to be generated (not allowed with explicit client-id)",
    type=int,
    default=1,
)
@click.option("--registry", help="The registry URL for the images", type=str)
@click.option(
    "--nowait", is_flag=True, help="Do not wait for the GefyraClient to be ready"
)
@click.pass_context
@standard_error_handler
def create_clients(ctx, client_id, quantity, registry, nowait: bool = False):
    from gefyra import api

    if quantity > 1 or not nowait:
        with alive_bar(
            total=None,
            length=20,
            title=f"Creating the requested GefyraClient (timeout=60))",
            bar="smooth",
            spinner="classic",
            stats=False,
            dual_line=True,
        ) as bar:
            client: GefyraClient = api.add_clients(
                client_id,
                quantity,
                registry=registry,
                kubeconfig=ctx.obj["kubeconfig"],
                kubecontext=ctx.obj["context"],
            )
            client[0].watch_events(bar.text)  # only one, checked
    else:
        api.add_clients(
            client_id,
            quantity,
            registry=registry,
            kubeconfig=ctx.obj["kubeconfig"],
            kubecontext=ctx.obj["context"],
        )
        console.success(f"{quantity} GefyraClient(s) created successfully")


@clients.command(
    "delete", alias=["rm", "remove"], help="Mark a GefyraClient for deletion"
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
            console.success(f"GefyraClient {_del} marked for deletion")


@clients.command("list", alias=["ls"], help="List all GefyraClients")
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
            c.state.value,
            c.state_transitions.get("CREATING", "Creating..."),
            c._wg_handshake or "-",
        ]
        for c in gefyraclients
    ]
    click.echo(
        tabulate(
            clients,
            headers=["ID", "STATE", "CREATED", "WIREGUARD HANDSHAKE"],
            tablefmt="plain",
        )
    )


@clients.command(
    "disconnect", alias=["deactivate", "stop"], help="Disconnect a GefyraClient"
)
@click.argument("client_id")
@click.pass_context
@standard_error_handler
def disconnect_client(ctx, client_id):
    from gefyra import api

    client = api.get_client(
        client_id, kubeconfig=ctx.obj["kubeconfig"], kubecontext=ctx.obj["context"]
    )
    client.deactivate_connection()
    console.success(f"GefyraClient {client.name} marked for disconnection")


@clients.command("inspect", alias=["show", "get"], help="Describe a GefyraClient")
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
    console.info("States:\n" + pprint.pformat(client.state_transitions, width=60))
    if client.wg_status:
        console.info("Wireguard: \n" + pprint.pformat(client.wg_status, width=60))


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
@click.option(
    "--registry",
    help="The registry URL for the images",
    type=str,
)
@click.option(
    "--mtu",
    help="The MTU for the Wireguard interface",
    type=int,
    default=1340,
)
@click.option(
    "--local",
    is_flag=True,
    help="Whether the target cluster is a local k8s cluster",
    default=False,
)
@click.pass_context
@standard_error_handler
def get_config(
    ctx,
    client_id,
    host,
    port,
    kube_api,
    output,
    registry,
    mtu,
    local: bool = False,
):
    from gefyra import api

    json_str = api.write_client_file(
        client_id,
        host=host,
        port=port,
        kube_api=kube_api,
        kubeconfig=ctx.obj["kubeconfig"],
        kubecontext=ctx.obj["context"],
        registry=registry,
        wireguard_mtu=mtu,
        local=local,
    )
    if output:
        output.write(json_str.encode("utf-8"))
    else:
        click.echo(json_str)
