import ast
import click
from gefyra.cli.utils import (
    OptionEatAll,
    check_connection_name,
    parse_env,
    parse_ip_port_map,
    parse_workload,
)


@click.command()
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
    callback=parse_ip_port_map,
)
@click.option(
    "--env-from",
    help="Copy the environment from the container in the notation 'Pod/Container'",
    type=str,
    callback=parse_workload,
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
    callback=parse_env,
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
@click.option(
    "--connection-name", type=str, callback=check_connection_name, required=False
)
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
    from gefyra import api

    if command:
        command = ast.literal_eval(command)[0]
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
