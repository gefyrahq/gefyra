import os
from typing import Optional
import click
from gefyra.cli import console
from gefyra.cli.utils import AliasedGroup, standard_error_handler
from tabulate import tabulate


@click.group("mount", cls=AliasedGroup, help="Manage GefyraBridgeMounts for a Gefyra installation")
@click.pass_context
def mount(ctx):
    # for management of mounts we always sourcing the kubeconfig and context from env if not passed
    if ctx.obj["kubeconfig"] is None:
        ctx.obj["kubeconfig"] = os.environ.get("KUBECONFIG") or os.path.expanduser(
            "~/.kube/config"
        )


@mount.command("create", help="Create a new Gefyra mount")
@click.option(
    "--namespace", help="The mount's target namespace", type=str, default="default"
)
@click.option(
    "--target",
    help=(
        "Intercept the container given in the notation 'resource/name/container'. "
        "Resource can be one of 'deployment' or 'pod'. "
        "E.g.: --target deployment/hello-nginx/nginx"
    ),
    required=True,
)
@click.option(
    "--provider", help="Provider for the bridge", type=str, default="carrier2"
)
@click.option(
    "--tls-key", help="Path to key file for tls traffic", type=str, required=False
)
@click.option(
    "--tls-certificate",
    help="Path to certificate file for tls traffic",
    type=str,
    required=False,
)
@click.option("--tls-sni", help="SNI for tls traffic", type=str, required=False)
@click.option("--connection-name", type=str, default="default")
@click.option("--wait", is_flag=True, help="Wait for the mount to be ready")
@click.option("--timeout", type=int, default=60, required=False)
@click.pass_context
def create(
    ctx,
    namespace: str,
    target: str,
    provider: str,
    connection_name: str = "",
    wait: bool = False,
    timeout: int = 0,
    tls_certificate: Optional[str] = None,
    tls_key: Optional[str] = None,
    tls_sni: Optional[str] = None,
):
    from gefyra import api

    api.mount(
        namespace=namespace,
        target=target,
        provider=provider,
        connection_name=connection_name,
        wait=wait,
        timeout=timeout,
        kubeconfig=ctx.obj["kubeconfig"],
        kubecontext=ctx.obj["context"],
        tls_certificate=tls_certificate,
        tls_key=tls_key,
        tls_sni=tls_sni,
    )


@mount.command(
    "delete", alias=["rm", "remove"], help="Mark a Gefyra mount for deletion"
)
@click.argument("mount_name", nargs=-1, required=True)
@click.pass_context
@standard_error_handler
def delete_mount(ctx, mount_name):
    from gefyra import api

    for _del in list(mount_name):
        deleted = api.delete_mount(
            _del, kubeconfig=ctx.obj["kubeconfig"], kubecontext=ctx.obj["context"]
        )
        if deleted:
            console.success(f"Client {_del} marked for deletion")


@mount.command("list", alias=["ls"], help="List all Gefyra mounts")
@click.pass_context
@standard_error_handler
def list_mounts(ctx):
    from gefyra import api

    bridge_mounts = api.list_mounts(
        kubeconfig=ctx.obj["kubeconfig"], kubecontext=ctx.obj["context"]
    )
    clients = [[c.name, c._state, c.target] for c in bridge_mounts]
    click.echo(tabulate(clients, headers=["ID", "STATE", "TARGET"], tablefmt="plain"))


@mount.command("describe", alias=["show", "get"], help="Describe a Gefyra mount")
@click.argument("mount_name")
@click.pass_context
@standard_error_handler
def inspect_mount(ctx, mount_name):
    from gefyra import api

    mount_obj = api.get_mount(
        mount_name, kubeconfig=ctx.obj["kubeconfig"], kubecontext=ctx.obj["context"]
    )
    console.heading(mount_obj.name)
    console.info(f"uid: {mount_obj.uid}")
    console.info(f"States: {mount_obj._state_transitions}")
