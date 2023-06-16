import ast
from click import pass_context
from gefyra import api
from .console import info
from .utils import AliasedGroup, OptionEatAll

import click
from prompt_toolkit import print_formatted_text

from alive_progress import config_handler, alive_bar

config_handler.set_global(bar="smooth", spinner="classic", stats=False, dual_line=True)

def _check_connection_name(selected) -> str:
    conn_list = api.list_connections()
    if not conn_list:
        raise click.UsageError(
            message="No Gefyra connection found. Please connect to a cluster first or run 'gefyra up'."
        )
    if selected and selected in [conn.name for conn in conn_list]:
        return selected
    elif selected:
        raise click.BadParameter(message=f"The connection name {selected} does not exist.")
    else:
        conn_names = [conn.name for conn in conn_list]
        if "default" in conn_names and len(conn_names) == 1:
            connection_name = "default"
        else:
            raise click.MissingParameter(
                message="Please provide a connection name from: {conn_names}",
                param="connection-name",
            )
        return connection_name

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

    if debug:
        logger = logging.getLogger()
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logging.getLogger("gefyra").setLevel(logging.DEBUG)
    else:
        logging.getLogger("gefyra").setLevel(logging.ERROR)
    ctx.ensure_object(dict)
    ctx.obj["kubeconfig"] = kubeconfig
    ctx.obj["context"] = context


@cli.group(
    "clients", cls=AliasedGroup, help="Manage clients for this Gefyra installation"
)
@click.pass_context
def clients(ctx):
    pass


@cli.group(
    "connections",
    cls=AliasedGroup,
    help="Manage connections to clusters for this Gefyra installation",
)
@click.pass_context
def connections(ctx):
    pass


@cli.command()
@click.option(
    "-n",
    "--no-check",
    help="Do not check whether there is a new version",
    is_flag=True,
    default=False,
)
@click.pass_context
def version(ctx, no_check):
    import requests
    import gefyra

    info(f"Gefyra client version: {gefyra.configuration.__VERSION__}")
    if not no_check:
        release = requests.get(
            "https://api.github.com/repos/gefyrahq/gefyra/releases/latest"
        )
        if release.status_code == 403:  # pragma: no cover
            info("Versions cannot be compared, as API rate limit was exceeded")
            return None
        latest_release_version = release.json()["tag_name"].replace("-", ".")
        if (
            gefyra.configuration.__VERSION__ != latest_release_version
        ):  # pragma: no cover
            info(
                f"You are using gefyra version {gefyra.configuration.__VERSION__}; however, version"
                f" {latest_release_version} is available."
            )
    return True


@cli.command()
@click.option(
    "-d",
    "--detach",
    help="Run container in background and print container ID",
    type=bool,
    default=False,
    is_flag=True,
)
@click.option(
    "--rm",
    "auto_remove",
    help="Automatically remove the container when it exits",
    type=bool,
    is_flag=True,
    default=False,
)
@click.option(
    "-p",
    "--expose",
    help="Add port mapping in form of <container_port>:<host_port>",
    type=str,
    multiple=True,
)  # TODO IpPortMappingParser
@click.option(
    "--env-from",
    help="Copy the environment from the container in the notation 'Pod/Container'",
    type=str,
)
@click.option(
    "-v",
    "--volume",
    help=(
        "Bind mount a volume into the container in notation src:dest, allowed multiple"
        " times"
    ),
    type=str,
    multiple=True,
)
@click.option(
    "--env",
    help=(
        "Set or override environment variables in the form ENV=value, allowed multiple"
        " times"
    ),
    type=str,
    multiple=True,
)
@click.option(
    "-n", "--namespace", help="The namespace for this container to run in", type=str
)
@click.option(
    "-c",
    "--command",
    help="The command for this container to in Gefyra",
    type=str,
    cls=OptionEatAll,
)
@click.option(
    "-N",
    "--name",
    help="The name of the container running in Gefyra",
    type=str,
    required=True,
)
@click.option(
    "-i", "--image", help="The docker image to run in Gefyra", type=str, required=True
)
@click.option("--connection-name", type=str)
def run(
    detach,
    auto_remove,
    expose,
    env_from,
    volume,
    env,
    namespace,
    command,
    name,
    image,
    connection_name,
):
    if command:
        command = ast.literal_eval(command)[0]
    connection_name = _check_connection_name()
    api.run(
        image=image,
        name=name,
        command=command,
        namespace=namespace,
        env_from=env_from,
        env=env,
        ports=expose,
        auto_remove=auto_remove,
        volumes=volume,
        detach=detach,
        connection_name=connection_name,
    )


@cli.command(
    "bridge", help="Establish a Gefyra bridge to a container in the cluster"
)
@click.option(
    "-N", "--name", help="The name of the container running in Gefyra", required=True
)
@click.option(
    "-p",
    "--ports",
    # help=port_mapping_help_text,
    required=True,
    # action=PortMappingParser,
)
@click.option(
    "-n",
    "--namespace",
    #   help=namespace_help_text,
    default="default",
)
@click.option(
    "-P",
    "--no-probe-handling",
    is_flag=True,
    help="Make Carrier to not handle probes during switch operation",
    default=False,
)
@click.option(
    "--target",
    help=(
        "Intercept the container given in the notation 'resource/name/container'. "
        "Resource can be one of 'deployment', 'statefulset' or 'pod'. "
        "E.g.: --target deployment/hello-nginx/nginx"
    ),
    required=True,
)
@click.option("--connection-name", type=str)
def create_bridge(name, ports, target, namespace, no_probe_handling, connection_name):
    connection_name = _check_connection_name(connection_name)
    api.bridge(
        name=name,
        ports=ports,
        target=target,
        namespace=namespace,
        handle_probes=no_probe_handling,
        timeout=10,
        connection_name=connection_name,
    )


def main():
    cli(obj={})


if __name__ == "__main__":
    main()

from .connections import *  # noqa
from .installation import *  # noqa
from .clients import *  # noqa
from .updown import *  # noqa
