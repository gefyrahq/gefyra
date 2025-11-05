import os
import click
from gefyra.cli.self import _self
from gefyra.cli.utils import AliasedGroup
from gefyra.cli.version import version
from gefyra.cli.run import run
from gefyra.cli.bridge import bridge
from gefyra.cli.connections import connections
from gefyra.cli.status import status_command
from gefyra.cli.telemetry import telemetry
from gefyra.cli.updown import cluster_down, cluster_up
from gefyra.cli.list import list
from gefyra.cli.mount import delete_mount, list_mounts, inspect_mount

from .context import cli


@click.group(
    "mount",
    cls=AliasedGroup,
    help="List and inspect GefyraBridgeMountss",
)
@click.pass_context
def mount(ctx):
    # for management of mounts we always sourcing the kubeconfig and context from env if not passed
    if ctx.obj["kubeconfig"] is None:
        ctx.obj["kubeconfig"] = os.environ.get("KUBECONFIG") or os.path.expanduser(
            "~/.kube/config"
        )


mount.add_command(list_mounts)
mount.add_command(delete_mount)
mount.add_command(inspect_mount)


cli.add_command(cmd=telemetry, name="telemetry")
cli.add_command(cmd=connections, name="connections")
cli.add_command(cmd=cluster_up, name="up")
cli.add_command(cmd=cluster_down, name="down")
cli.add_command(cmd=status_command, name="status")
cli.add_command(cmd=bridge, name="bridge")
cli.add_command(cmd=run, name="run")
cli.add_command(cmd=version, name="version")
cli.add_command(cmd=_self, name="self")
cli.add_command(cmd=list, name="list")
cli.add_command(cmd=mount, name="mount")
# cli.add_command(cmd=reverse, name="reverse")


def main():
    cli(obj={"mode": "client"})


if __name__ == "__main__":
    main()
