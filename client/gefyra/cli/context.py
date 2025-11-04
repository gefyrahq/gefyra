import click
import urllib3

from gefyra.cli.utils import AliasedGroup


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
def cli(ctx: click.Context, kubeconfig, context, debug):
    import logging
    from gefyra.cli.telemetry import CliTelemetry

    # Set up logging based on the debug flag
    if debug:
        from kubernetes.client import Configuration

        k8s_client_config = Configuration.get_default_copy()
        k8s_client_config.debug = True
        Configuration.set_default(k8s_client_config)

        logger = logging.getLogger()
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(levelname)s %(name)s %(filename)s:%(lineno)d - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logging.getLogger("gefyra").setLevel(logging.DEBUG)
    else:
        urllib3.disable_warnings()
        logging.getLogger("gefyra").setLevel(logging.ERROR)

    ctx.ensure_object(dict)

    try:
        ctx.obj["telemetry"] = CliTelemetry()
    except Exception:  # pragma: no cover
        ctx.obj["telemetry"] = False
    ctx.obj["debug"] = debug
    ctx.obj["kubeconfig"] = kubeconfig
    ctx.obj["context"] = context
