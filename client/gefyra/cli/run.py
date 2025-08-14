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
    "--cpu-from",
    help="Inherit CPU limit from a workload, e.g. 'pod/<name>' or 'deployment/<name>'",
    type=str,
    required=False,
)
@click.option(
    "--memory-from",
    help="Inherit memory limit from a workload, e.g. 'pod/<name>' or 'deployment/<name>'",
    type=str,
    required=False,
)
@click.option(
    "--cpu",
    help="CPU limit for the container (e.g. '500m' or '2')",
    type=str,
    required=False,
)
@click.option(
    "--memory",
    help="Memory limit for the container (e.g. '512Mi', '1Gi', or '1g')",
    type=str,
    required=False,
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
    "--pull",
    type=click.Choice(["always", "missing"], case_sensitive=False),
    help="Define whether image should always be pulled",
    required=False,
    default="missing",
)
@click.option(
    "--platform",
    type=str,
    help="Define platform for image pull. Default: linux/amd64",
    required=False,
    default="linux/amd64",
)
@click.option(
    "--connection-name", type=str, callback=check_connection_name, required=False
)
def run(
    detach,
    auto_remove,
    expose,
    env_from,
    cpu_from,
    memory_from,
    cpu,
    memory,
    volume,
    env,
    namespace,
    command,
    name,
    image,
    pull,
    platform,
    connection_name,
):
    from gefyra import api

    if command:
        command = ast.literal_eval(command)[0]
    # Validate mutually exclusive options
    if memory and memory_from:
        raise click.UsageError(
            "Option conflict: --memory and --memory-from cannot be used together. Please specify only one."
        )
    if cpu and cpu_from:
        raise click.UsageError(
            "Option conflict: --cpu and --cpu-from cannot be used together. Please specify only one."
        )

    result = api.run(
        image=image,
        name=name,
        command=command,
        namespace=namespace,
        env_from=env_from,
        cpu_from=cpu_from,
        memory_from=memory_from,
        cpu=cpu,
        memory=memory,
        env=env,
        ports=expose,
        auto_remove=auto_remove,
        volumes=volume,
        detach=detach,
        pull=pull,
        platform=platform,
        connection_name=connection_name,
    )
    if not result:
        exit(1)
