import logging
import click

from gefyra.misc.comps import COMPONENTS
from gefyra.api.install import LB_PRESETS

from gefyra.cli.utils import (
    installoptions_to_cli_options,
    multi_options,
    standard_error_handler,
)


@click.command(
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
    help=f"Set configs from a preset (available: {','.join(LB_PRESETS.keys())})",
    type=str,
)
@click.option(
    "--apply",
    is_flag=True,
)
@click.option(
    "--wait",
    is_flag=True,
)
@click.pass_context
@multi_options(installoptions_to_cli_options())
@standard_error_handler
def install(ctx, component, preset, apply, wait, **kwargs):
    from alive_progress import alive_bar
    from gefyra import api

    if not all(kwargs.values()):
        kwargs = {}
    if wait and not apply:
        raise click.BadOptionUsage(
            option_name="wait", message="Cannot wait without '--apply'"
        )
    if wait:
        logger = logging.getLogger("gefyra")
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter("%(message)s")
        if len(logger.handlers) > 0:
            logger.handlers[0].setFormatter(formatter)
        else:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            logger.addHandler(handler)
    if apply:
        with alive_bar(
            total=None,
            length=20,
            title="Installing Gefyra",
            bar="smooth",
            spinner="classic",
            stats=False,
            dual_line=True,
        ):
            ouput = api.install(component, preset, apply, wait, **kwargs)
    else:
        ouput = api.install(component, preset, apply, wait, **kwargs)
    if not apply:
        click.echo(ouput)


@click.command("uninstall", help="Removes the Gefyra installation from the cluster")
@click.option("--force", "-f", help="Delete without promt", is_flag=True)
@standard_error_handler
def uninstall(force):
    from alive_progress import alive_bar
    from gefyra import api

    if not force:
        click.confirm(
            "Do you want to remove all Gefyra components from this cluster?",
            abort=True,
        )
    with alive_bar(
        total=None,
        length=20,
        title="Uninstalling all Gefyra components from the cluster",
        bar="smooth",
        spinner="classic",
        stats=False,
        dual_line=True,
    ):
        api.uninstall()
