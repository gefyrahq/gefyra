import dataclasses

import click

from gefyra.misc.comps import COMPONENTS
from gefyra.misc.install import synthesize_config_as_yaml
from gefyra.misc.uninstall import (
    remove_all_clients,
    remove_gefyra_namespace,
    remove_remainder_bridges,
)
from gefyra.types import GefyraInstallOptions

from gefyra.cli.console import error, info
from gefyra.cli.utils import (
    installoptions_to_cli_options,
    multi_options,
    standard_error_handler,
)
from gefyra.cli.__main__ import cli as _cli

PRESETS = {
    "aws": GefyraInstallOptions(
        service_type="LoadBalancer",
        service_annotations={
            "service.beta.kubernetes.io/aws-load-balancer-type": "external",
            "service.beta.kubernetes.io/aws-load-balancer-nlb-target-type": "ip",
            "service.beta.kubernetes.io/aws-load-balancer-healthcheck-port": "80",
            "service.beta.kubernetes.io/aws-load-balancer-healthcheck-protocol": "TCP",
            "service.beta.kubernetes.io/aws-load-balancer-healthcheck-healthy-threshold": "3",
            "service.beta.kubernetes.io/aws-load-balancer-healthcheck-unhealthy-threshold": "3",
            "service.beta.kubernetes.io/aws-load-balancer-healthcheck-timeout": "10",
            "service.beta.kubernetes.io/aws-load-balancer-healthcheck-interval": "10",
            "service.beta.kubernetes.io/aws-load-balancer-scheme": "internet-facing",
        },
    ),
}


@_cli.command(
    "install",
    help="Create and print the Kubernetes configs for Gefyra; use it so 'gefyra install [options] | kubectl apply -f -",
)
@click.option(
    "--component",
    "--comp",
    help=f"Limit config creation to this component (available: {','.join([c.__name__.split('.')[-1] for c in COMPONENTS])})",
    type=str,
    multiple=True,
)
@click.option(
    "--preset",
    help=f"Set configs from a preset (available: {','.join(PRESETS.keys())})",
    type=str,
)
@click.pass_context
@multi_options(installoptions_to_cli_options())
def install(ctx, component, preset, **kwargs):
    if preset:
        presetoptions = PRESETS.get(preset)
        if not presetoptions:
            raise RuntimeError(f"Preset {preset} not available. ")
        presetoptions = dataclasses.asdict(presetoptions)
        presetoptions.update({k: v for k, v in kwargs.items() if v is not None})
        options = GefyraInstallOptions(**presetoptions)
    else:
        options = GefyraInstallOptions(
            **{k: v for k, v in kwargs.items() if v is not None}
        )
    click.echo(synthesize_config_as_yaml(options=options, components=component))


@_cli.command("uninstall", help="Removes the Gefyra installation from the cluster")
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
