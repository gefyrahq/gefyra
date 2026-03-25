import ast
import warnings

import click
from gefyra.cli.utils import (
    OptionEatAll,
    check_connection_name,
    parse_env,
    parse_extra_container_args,
    parse_ip_port_map,
    parse_workload,
)


@click.command(
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True,
    ),
)
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
    help="Inherit CPU limit from a workload, e.g. 'pod/<name>', 'deployment/<name>' or 'statefulset/<name>'",
    type=str,
    required=False,
)
@click.option(
    "--memory-from",
    help="Inherit memory limit from a workload, e.g. 'pod/<name>', 'deployment/<name>' or 'statefulset/<name>'",
    type=str,
    required=False,
)
@click.option(
    "--cpu",
    help="[Deprecated: use -- --cpu-quota <value> instead] CPU limit for the container (e.g. '500m' or '2')",
    type=str,
    required=False,
)
@click.option(
    "--memory",
    help="[Deprecated: use -- --mem-limit <value> instead] Memory limit for the container (e.g. '512Mi', '1Gi', or '1g')",
    type=str,
    required=False,
)
@click.option(
    "--user",
    help="Username or UID (format: <name|uid>[:<group|gid>])",
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
    "--security-opt",
    type=str,
    help="Security Options",
    required=False,
    multiple=True,
    default=[],
)
@click.option(
    "--connection-name", type=str, callback=check_connection_name, required=False
)
@click.option(
    "--privileged",
    "privileged",
    help="Give extended privileges to this container",
    type=bool,
    is_flag=True,
    default=False,
)
@click.pass_context
def run(
    ctx,
    detach,
    auto_remove,
    expose,
    env_from,
    cpu_from,
    memory_from,
    cpu,
    memory,
    user,
    volume,
    env,
    namespace,
    command,
    name,
    image,
    pull,
    platform,
    connection_name,
    security_opt,
    privileged,
):
    """Run a container in Gefyra.

    \b
    Any additional container engine arguments can be passed after the known
    options.  They are forwarded directly to the Docker/Podman API.
    Use the docker-py parameter names with '--' prefix and '-' separators:

    \b
      gefyra run -i myimage -N myname -- --cpu-shares 512 --mem-reservation 256m
      gefyra run -i myimage -N myname -- --cpu-period 100000 --cpu-quota 50000

    \b
    See https://docker-py.readthedocs.io/en/stable/containers.html for the
    full list of supported parameters.
    """
    from gefyra import api

    if cpu:
        warnings.warn(
            "--cpu is deprecated; pass the equivalent docker-py argument instead, "
            "e.g.: -- --cpu-quota <value>",
            FutureWarning,
            stacklevel=1,
        )
    if memory:
        warnings.warn(
            "--memory is deprecated; pass the equivalent docker-py argument instead, "
            "e.g.: -- --mem-limit <value>",
            FutureWarning,
            stacklevel=1,
        )

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

    # Parse extra container engine args from ctx.args
    extra_container_args = parse_extra_container_args(ctx.args) if ctx.args else None

    security_opt = list(security_opt)
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
        user=user,
        env=env,
        ports=expose,
        auto_remove=auto_remove,
        volumes=volume,
        detach=detach,
        pull=pull,
        platform=platform,
        security_opts=security_opt,
        privileged=privileged,
        connection_name=connection_name,
        extra_container_args=extra_container_args,
    )
    if not result:
        exit(1)
