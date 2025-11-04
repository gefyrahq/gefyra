from .context import cli

from gefyra.cli.clients import clients
from gefyra.cli.bridge import bridge
from gefyra.cli.operator import operator
from gefyra.cli.installation import install, uninstall
from gefyra.cli.mount import mount
from gefyra.cli.status import status_command
from gefyra.cli.version import version
from gefyra.cli.self import _self
from gefyra.cli.telemetry import telemetry

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
