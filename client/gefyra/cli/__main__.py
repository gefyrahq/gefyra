from .utils import AliasedGroup

import click
from prompt_toolkit import print_formatted_text

from gefyra.configuration import ClientConfiguration


@click.group(cls=AliasedGroup)
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
def cli(ctx, kubeconfig, context, debug):
    ctx.ensure_object(dict)
    ctx.obj["config"] = ClientConfiguration()


@cli.group(
    "clients", cls=AliasedGroup, help="Manage clients for this Gefyra installation"
)
@click.pass_context
def clients(ctx):
    pass


@cli.command()
@click.pass_context
def version(ctx):
    from gefyra.configuration import __VERSION__

    print_formatted_text("Gefyra version: " + __VERSION__)


def main():
    cli(obj={})


if __name__ == "__main__":
    main()

from .install import *  # noqa
from .clients import *  # noqa
