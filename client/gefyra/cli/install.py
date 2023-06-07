import click

import gefyra.api as api

from gefyra.misc.comps import COMPONENTS
from gefyra.misc.uninstall import (
    remove_all_clients,
    remove_gefyra_namespace,
    remove_remainder_bridges,
)

from gefyra.cli.console import error
from gefyra.cli.utils import installoptions_to_cli_options, multi_options
from gefyra.cli.main import cli


@cli.command(
    "install",
    help=(
        "Create and print the Kubernetes configs for Gefyra; usage: 'gefyra install"
        " [options] | kubectl apply -f -"
    ),
)
@click.option(
    "--component",
    "--comp",
    help=(
        "Limit config creation to this component (available:"
        f" {','.join([c.__name__.split('.')[-1] for c in COMPONENTS])})"
    ),
    type=str,
    multiple=True,
)
@click.option(
    "--preset",
    help=f"Set configs from a preset (available: {','.join(api.LB_PRESETS.keys())})",
    type=str,
)
@click.pass_context
@multi_options(installoptions_to_cli_options())
def install(ctx, component, preset, **kwargs):
    click.echo(api.install(component, preset, **kwargs))


@cli.command("uninstall", help="Removes the Gefyra installation from the cluster")
@click.option("--force", "-f", help="Delete without promt", is_flag=True)
@click.option(
    "--namespace",
    "-ns",
    help="The namespace Gefyra was installed to (default: gefyra)",
    type=str,
)
@click.pass_context
def uninstall(ctx, force, namespace):
    if not force:
        click.confirm(
            "Do you want to remove all Gefyra components from this cluster?",
            abort=True,
        )
    if namespace:
        ctx.obj["config"].NAMESPACE = namespace
    click.echo("Removing all Gefyra bridges")
    try:
        remove_remainder_bridges(config=ctx.obj["config"])
    except Exception as e:
        error(str(e))

    click.echo("Removing remainder Gefyra clients")
    try:
        remove_all_clients(config=ctx.obj["config"])
    except Exception as e:
        error(str(e))

    click.echo("Removing Gefyra namespace")
    try:
        remove_gefyra_namespace(config=ctx.obj["config"])
    except Exception as e:
        error(str(e))
