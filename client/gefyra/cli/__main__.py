from gefyra import api
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
def cli(ctx: click.Context, kubeconfig, context, debug):
    if debug:
        import logging

        logging.getLogger("gefyra").setLevel(logging.DEBUG)
    ctx.ensure_object(dict)
    ctx.obj["config"] = ClientConfiguration()


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
@click.pass_context
def version(ctx):
    from gefyra.configuration import __VERSION__

    print_formatted_text("Gefyra version: " + __VERSION__)


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
    "--env_from",
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
    "-c", "--command", help="The command for this container to in Gefyra", type=str
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
@click.option("--connection-name", type=str, required=True)
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
    configuration = ClientConfiguration()
    api.run(
        image=image,
        name=name,
        command=" ".join(command) if command else None,
        namespace=namespace,
        env_from=env_from,
        env=env,
        ports=expose,
        auto_remove=auto_remove,
        volumes=volume,
        config=configuration,
        detach=detach,
        connection_name=connection_name,
    )


def main():
    cli(obj={})


if __name__ == "__main__":
    main()

from .connect import *  # noqa
from .install import *  # noqa
from .clients import *  # noqa
