import os
import click
from gefyra.cli.utils import AliasedGroup
from .context import cli

from gefyra.cli.clients import clients
from gefyra.cli.bridge import list_bridges, delete_bridge, inspect_bridge
from gefyra.cli.operator import operator
from gefyra.cli.installation import install, uninstall
from gefyra.cli.mount import mount
from gefyra.cli.status import status_command
from gefyra.cli.version import version
from gefyra.cli.self import _self
from gefyra.cli.telemetry import telemetry


@click.group(
    "bridge",
    cls=AliasedGroup,
    help="List and remove GefyraBridges",
)
@click.pass_context
def bridge(ctx):
    # for management of bridges we always sourcing the kubeconfig and context from env if not passed
    if ctx.obj["kubeconfig"] is None:
        ctx.obj["kubeconfig"] = os.environ.get("KUBECONFIG") or os.path.expanduser(
            "~/.kube/config"
        )


bridge.add_command(list_bridges)
bridge.add_command(delete_bridge)
bridge.add_command(inspect_bridge)

cli.add_command(cmd=bridge, name="bridge")
cli.add_command(cmd=clients, name="clients")
cli.add_command(cmd=install, name="install")
cli.add_command(cmd=uninstall, name="uninstall")
cli.add_command(cmd=status_command, name="status")
cli.add_command(cmd=version, name="version")
cli.add_command(cmd=_self, name="self")
cli.add_command(cmd=operator, name="operator")
cli.add_command(cmd=mount, name="mount")
cli.add_command(cmd=telemetry, name="telemetry")


def main():
    cli(obj={"mode": "adm"})


if __name__ == "__main__":
    main()
