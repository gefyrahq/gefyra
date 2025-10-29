import os
from typing import Optional
from alive_progress import alive_bar
import click
from gefyra.cli import console
from gefyra.cli.utils import AliasedGroup, standard_error_handler
from gefyra.types import GefyraBridgeMount
from tabulate import tabulate


@click.group(
    "mount",
    cls=AliasedGroup,
    help="Manage GefyraBridgeMounts for a Gefyra installation",
)
@click.pass_context
def mount(ctx):
    # for management of mounts we always sourcing the kubeconfig and context from env if not passed
    if ctx.obj["kubeconfig"] is None:
        ctx.obj["kubeconfig"] = os.environ.get("KUBECONFIG") or os.path.expanduser(
            "~/.kube/config"
        )


@mount.command("create", help="Create a new GefyraBridgeMount in the cluster")
@click.option(
    "--namespace",
    help="The GefyraBridgeMount's target namespace",
    type=str,
    default="default",
)
@click.option(
    "--name",
    help="Assign a custom name to this GefyraBridgeMount",
    type=str,
    required=False,
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
@click.option(
    "--nowait", is_flag=True, help="Do not wait for the GefyraBridgeMount to be ready"
)
@click.option("--timeout", type=int, default=60, required=False)
@click.pass_context
def create(
    ctx,
    namespace: str,
    target: str,
    connection_name: str = "",
    nowait: bool = False,
    timeout: int = 0,
    name: Optional[str] = None,
    tls_certificate: Optional[str] = None,
    tls_key: Optional[str] = None,
    tls_sni: Optional[str] = None,
):
    from gefyra import api

    try:
        with alive_bar(
            total=None,
            length=20,
            title=f"Creating the requested GefyraBridgeMount (timeout={timeout}s))",
            bar="smooth",
            spinner="classic",
            stats=False,
            dual_line=True,
        ) as bar:

            mount: GefyraBridgeMount = api.create_mount(
                namespace=namespace,
                target=target,
                provider="duplicate",
                connection_name=connection_name,
                wait=False,
                timeout=timeout,
                kubeconfig=ctx.obj["kubeconfig"],
                kubecontext=ctx.obj["context"],
                mount_name=name,
                tls_certificate=tls_certificate,
                tls_key=tls_key,
                tls_sni=tls_sni,
            )
            bar.text(f"GefyraBridgeMount requested")
            if not nowait:
                mount.watch_events(bar.text, timeout=timeout)
        console.success(
            f"Successfully created GefyraBridgeMount '{mount.name}'. You can now create a GefyraBridge to intercept traffic."
        )

    except RuntimeError as e:
        console.error(f"Could not create GefyraBridgeMount: {e}")


@mount.command(
    "delete", alias=["rm", "remove"], help="Mark a GefyraBridgeMount for deletion"
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
            console.success(f"GefyraBridgeMount '{_del}' marked for deletion")


@mount.command("list", alias=["ls"], help="List all GefyraBridgeMounts")
@click.pass_context
@standard_error_handler
def list_mounts(ctx):
    from gefyra import api

    bridge_mounts = api.list_mounts(
        kubeconfig=ctx.obj["kubeconfig"], kubecontext=ctx.obj["context"]
    )
    mounts = [[c.name, c._state, c.target, c.target_namespace] for c in bridge_mounts]
    if mounts:
        click.echo(
            tabulate(
                mounts, headers=["ID", "STATE", "TARGET", "NAMESPACE"], tablefmt="plain"
            )
        )
    else:
        console.info("No GefyraBridgeMounts found")


@mount.command(
    "inspect", alias=["describe", "show", "get"], help="Describe a GefyraBridgeMount"
)
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
    console.heading("Events")
    mount_obj.watch_events(console.info, None, 1)
