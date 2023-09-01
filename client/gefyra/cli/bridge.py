import dataclasses
from time import sleep
import click
from gefyra.cli import console
from gefyra.cli.utils import (
    check_connection_name,
    parse_ip_port_map,
    standard_error_handler,
)
from tabulate import tabulate


@click.command("bridge", help="Establish a Gefyra bridge to a container in the cluster")
@click.option(
    "-N", "--name", help="The name of the container running in Gefyra", required=True
)
@click.option(
    "-p",
    "--ports",
    help="Add forward port mapping in form of <remote_container_port>:<local_container_port>",
    required=True,
    multiple=True,
    callback=parse_ip_port_map,
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
@click.option(
    "--connection-name", type=str, default="default", callback=check_connection_name
)
@click.option("--timeout", type=int, default=60, required=False)
@standard_error_handler
def create_bridge(
    name, ports, target, namespace, no_probe_handling, connection_name, timeout
):
    from alive_progress import alive_bar
    from gefyra import api

    print_keys = {
        "name": "NAME",
        "port_mappings": "PORTS",
        "local_container_ip": "LOCAL ADDRESS",
        "target_container": "TARGET CONTAINER",
        "target_pod": "TARGET POD",
        "target_namespace": "NAMESPACE",
    }
    # we are not blocking this call
    _created_bridges = api.bridge(
        name=name,
        ports=ports,
        target=target,
        namespace=namespace,
        handle_probes=no_probe_handling,
        wait=False,
        connection_name=connection_name,
    )
    with alive_bar(
        total=None,
        length=20,
        title=f"Creating the requested bridge(s) (timeout={timeout}))",
        bar="smooth",
        spinner="classic",
        stats=False,
        dual_line=True,
    ) as bar:
        for _i in range(timeout):
            all_bridges = api.list_gefyra_bridges(connection_name=connection_name)[0][1]
            _created_bridges = [
                bridge
                for bridge in all_bridges
                if bridge.name in [_bridge.name for _bridge in _created_bridges]
            ]
            bar.text(
                "\n".join(
                    [f"{bridge.name}: {bridge.state}" for bridge in _created_bridges]
                )
            )
            if all(bridge.state == "ACTIVE" for bridge in _created_bridges):
                break
            else:
                sleep(1)
        bar.text(f"{len(_created_bridges)} bridge(s) active")

    if _created_bridges:
        bridges_print = [
            {
                k: v
                for k, v in dataclasses.asdict(bridge).items()
                if k in print_keys.keys()
            }
            for bridge in _created_bridges
        ]
        console.success(
            "The following bridges have been created. Run 'gefyra list --bridges' to see all bridges."
        )
        click.echo(
            tabulate(
                bridges_print,
                headers=print_keys,
                tablefmt="plain",
            )
        )


@click.command("unbridge", help="Remove a Gefyra bridge (from 'gefyra list --bridges')")
@click.argument("name", required=False)
@click.option(
    "-A",
    "--all",
    help="Unbridge all bridges",
    required=False,
    is_flag=True,
    default=False,
)
@click.option(
    "--connection-name", type=str, default="default", callback=check_connection_name
)
@standard_error_handler
def unbridge(name: str, connection_name: str, all: bool = False):
    from gefyra import api

    if not all and not name:
        console.error("Provide a name or use --all flag to unbridge.")
    if all:
        api.unbridge_all(connection_name=connection_name, wait=True)
    else:
        api.unbridge(connection_name=connection_name, name=name, wait=True)
