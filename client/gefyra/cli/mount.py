import json
import os
from typing import Optional, Literal
from alive_progress import alive_bar
import click
from gefyra.cli import console
from gefyra.cli.utils import AliasedGroup, check_connection_name, standard_error_handler
from gefyra.exceptions import CommandTimeoutError
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
        "Install a GefyraBridgeMount to workloads following the notion 'resource/name/container'. "
        "Resource can be one of 'deployment', 'statefulset' or 'pod'. "
        "E.g.: --target deployment/hello-nginx/nginx"
    ),
    required=True,
)
@click.option(
    "--tls-key",
    help="Path to key file for tls traffic (within the target container).",
    type=str,
    required=False,
)
@click.option(
    "--tls-certificate",
    help="Path to certificate file for tls traffic (within the target container).",
    type=str,
    required=False,
)
@click.option(
    "--tls-sni",
    help="SNI for tls traffic (within the target container).",
    type=str,
    required=False,
)
@click.option("--connection-name", "-c", type=str, default="default")
@click.option(
    "--nowait", is_flag=True, help="Do not wait for the GefyraBridgeMount to be ready"
)
@click.option("--timeout", type=int, default=60, required=False)
@click.pass_context
@standard_error_handler
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

    timeout_reached = False
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
                provider="carrier2mount",
                connection_name=connection_name,
                wait=not nowait,
                timeout=timeout,
                kubeconfig=ctx.obj["kubeconfig"],
                kubecontext=ctx.obj["context"],
                mount_name=name,
                tls_certificate=tls_certificate,
                tls_key=tls_key,
                tls_sni=tls_sni,
            )
            bar.text("GefyraBridgeMount requested")
            if not nowait:
                timeout_reached = mount.watch_events(bar.text, timeout=timeout)
        if timeout_reached:
            raise CommandTimeoutError("Timeout for this operation reached.")
        else:
            console.success(
                f"Successfully created GefyraBridgeMount '{mount.name}'. {'You can now create a GefyraBridge to intercept traffic.' if not nowait else ''}"
            )

    except RuntimeError as e:
        raise click.ClickException(f"Could not create GefyraBridgeMount: {e}")


@mount.command(
    "delete", alias=["rm", "remove"], help="Mark a GefyraBridgeMount for deletion"
)
@click.option(
    "--nowait",
    is_flag=True,
    help="Do not wait for the GefyraBridgeMount to be deleted.",
)
@click.option("--connection-name", "-c", type=str, default="default")
@click.argument("mount_name", nargs=-1, required=True)
@click.option("--timeout", type=int, default=60, required=False)
@click.pass_context
@standard_error_handler
def delete_mount(
    ctx,
    mount_name,
    nowait: bool = False,
    timeout: int = 60,
    connection_name: str = "default",
):
    from gefyra import api

    # TODO add connection-name support
    for _del in list(mount_name):
        try:
            deleted = api.delete_mount(
                _del,
                kubeconfig=ctx.obj["kubeconfig"],
                kubecontext=ctx.obj["context"],
                wait=not nowait,
                timeout=timeout,
                connection_name=connection_name,
            )
        except TimeoutError:
            raise CommandTimeoutError("Timeout for deleting GefyraBridgeMount exceeded")
        if deleted:
            console.success(f"GefyraBridgeMount '{_del}' marked for deletion")


@mount.command("list", alias=["ls"], help="List all GefyraBridgeMounts")
@click.option("--output", "-o", type=click.Choice(["json", "text"]), default="text")
@click.option("--connection-name", type=str, default="default")
@click.pass_context
@standard_error_handler
def list_mounts(
    ctx, output: Literal["json", "text"] = "text", connection_name: str = "default"
):
    from gefyra import api

    bridge_mounts = api.list_mounts(
        kubeconfig=ctx.obj["kubeconfig"],
        kubecontext=ctx.obj["context"],
        connection_name=connection_name,
    )

    if bridge_mounts:
        if output == "text":
            mounts = [
                [c.name, c._state, c.target, c.target_container, c.target_namespace]
                for c in bridge_mounts
            ]
            click.echo(
                tabulate(
                    mounts,
                    headers=[
                        "ID",
                        "STATE",
                        "TARGET",
                        "TARGET CONTAINER",
                        "TARGET NAMESPACE",
                    ],
                    tablefmt="plain",
                )
            )
        elif output == "json":
            res = {mount.name: mount.inspect() for mount in bridge_mounts}
            click.echo(json.dumps(res))
        else:
            raise ValueError(f"Unsupported output format: {output}")
    else:
        console.info("No GefyraBridgeMounts found")


@mount.command(
    "inspect", alias=["describe", "show", "get"], help="Describe a GefyraBridgeMount"
)
@click.argument("mount_name")
@click.option("-o", "--output", type=click.Choice(["json", "text"]), default="text")
@click.option(
    "--connection-name", type=str, default="default", callback=check_connection_name
)
@click.pass_context
@standard_error_handler
def inspect_mount(
    ctx,
    mount_name,
    output: Literal["json", "text"] = "text",
    connection_name: str = "default",
):
    from gefyra import api

    # TODO add connection-name support
    mount_obj = api.get_mount(
        mount_name,
        kubeconfig=ctx.obj["kubeconfig"],
        kubecontext=ctx.obj["context"],
        connection_name=connection_name,
    )
    status = mount_obj.inspect(fetch_events=True)
    if output == "text":
        console.heading(status["name"])
        console.info(f"uid: {status['uid']}")
        console.info(
            f"Target: {status['target']} in namespace {status['target_namespace']}"
        )
        console.info(f"States: {status['_state_transitions']}")
        if "events" in status:
            console.heading("Events")
            for event in status["events"]:
                console.info(event)
    elif output == "json":
        click.echo(json.dumps(status))
    else:
        raise ValueError(f"Unsupported output format: {output}")
