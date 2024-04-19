import click

from gefyra.cli.self import _self
from gefyra.cli.version import version
from gefyra.cli.run import run
from gefyra.cli.bridge import create_bridge, unbridge
from gefyra.cli.clients import clients
from gefyra.cli.connections import connections
from gefyra.cli.installation import install, uninstall
from gefyra.cli.status import status_command
from gefyra.cli.telemetry import telemetry
from gefyra.cli.updown import cluster_down, cluster_up
from gefyra.cli.list import list
from gefyra.cli.utils import AliasedGroup


@click.group(
    cls=AliasedGroup,
)
@click.option(
    "--kubeconfig",
    help="Path to the kubeconfig file to use instead of loading the default",
)
@click.option(
    "--context",
    help="Context of the kubeconfig file to use instead of 'default'",
)
@click.option("-d", "--debug", default=False, is_flag=True)
@click.pass_context
def cli(ctx: click.Context, kubeconfig, context, debug):
    import logging
    from gefyra.cli.telemetry import CliTelemetry

    if debug:
        logger = logging.getLogger()
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(levelname)s %(name)s %(filename)s:%(lineno)d - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logging.getLogger("gefyra").setLevel(logging.DEBUG)
    else:
        logging.getLogger("gefyra").setLevel(logging.ERROR)
    ctx.ensure_object(dict)

    try:
        ctx.obj["telemetry"] = CliTelemetry()
    except Exception:  # pragma: no cover
        ctx.obj["telemetry"] = False
    ctx.obj["kubeconfig"] = kubeconfig
    ctx.obj["context"] = context


cli.add_command(cmd=telemetry, name="telemetry")
cli.add_command(cmd=connections, name="connections")
cli.add_command(cmd=clients, name="clients")
cli.add_command(cmd=install, name="install")
cli.add_command(cmd=uninstall, name="uninstall")
cli.add_command(cmd=cluster_up, name="up")
cli.add_command(cmd=cluster_down, name="down")
cli.add_command(cmd=status_command, name="status")
cli.add_command(cmd=create_bridge, name="bridge")
cli.add_command(cmd=unbridge, name="unbridge")
cli.add_command(cmd=run, name="run")
cli.add_command(cmd=version, name="version")
cli.add_command(cmd=list, name="list")
cli.add_command(cmd=_self, name="self")


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
