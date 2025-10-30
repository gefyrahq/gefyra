import dataclasses
import os
from time import sleep
from typing import List, Optional
from alive_progress import alive_bar
import click
from gefyra.types import ExactMatchHeader
from gefyra.cli import console
from gefyra.cli.utils import (
    AliasedGroup,
    check_connection_name,
    parse_ip_port_map,
    parse_match_header,
    standard_error_handler,
)
from gefyra.types.bridge import GefyraBridge
from tabulate import tabulate


@click.group(
    "bridge",
    cls=AliasedGroup,
    help="Manage GefyraBridge for a Gefyra installation",
)
@click.pass_context
def bridge(ctx):
    # for management of bridges we always sourcing the kubeconfig and context from env if not passed
    if ctx.obj["kubeconfig"] is None:
        ctx.obj["kubeconfig"] = os.environ.get("KUBECONFIG") or os.path.expanduser(
            "~/.kube/config"
        )


@bridge.command(
    "create",
    help="Establish a GefyraBridge from a GefyraBridgeMount in the cluster to a local container",
)
@click.option(
    "-N",
    "--name",
    "--target",
    help="The name of the local container running in Gefyra",
    required=True,
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
    "--match-header",
    help="Match header to forward traffic based to this client. E.g.: --matchHeader name:x-gefyra:peer",
    required=True,
    multiple=True,
    callback=parse_match_header,
)
@click.option(
    "-P",
    "--no-probe-handling",
    is_flag=True,
    help="Make Carrier to not handle probes during switch operation",
    default=False,
)
@click.option(
    "--mount",
    help="The target GefyraBridgeMount to install this GefyraBridge on",
    required=True,
)
@click.option(
    "--connection-name", type=str, default="default", callback=check_connection_name
)
@click.option(
    "--nowait", is_flag=True, help="Do not wait for the GefyraBridgeMount to be ready"
)
@click.option("--timeout", type=int, default=60, required=False)
@standard_error_handler
def create_bridge(
    name,
    ports,
    mount,
    match_header: List[ExactMatchHeader],
    no_probe_handling,
    connection_name,
    nowait,
    timeout,
):
    from gefyra import api

    with alive_bar(
        total=None,
        length=20,
        title=f"Creating the requested GefyraBridge (timeout={timeout}s))",
        bar="smooth",
        spinner="classic",
        stats=False,
        dual_line=True,
    ) as bar:

        bridge: GefyraBridge = api.create_bridge(
            name=name,
            ports=ports,
            bridge_mount_name=mount,
            connection_name=connection_name,
            match_header=match_header,
        )
        bar.text(f"GefyraBridge requested")
        if not nowait:
            bridge.watch_events(bar.text, timeout=timeout)
    # TODO check bridge state
    # console.success(f"Successfully created GefyraBridge '{bridge.name}'.")


@bridge.command(
    "delete", alias=["rm", "remove"], help="Mark a GefyraBridge for deletion"
)
@click.argument("name", required=False)
@click.option(
    "-A",
    "--all",
    help="Unbridge all GefyraBridges with local target containers",
    required=False,
    is_flag=True,
    default=False,
)
@click.option(
    "-m",
    "--mount",
    help="Unbridge all bridges for a specific mount",
    required=False,
    default=None,
)
@click.option(
    "--connection-name", type=str, default="default", callback=check_connection_name
)
@standard_error_handler
def delete_bridge(
    name: str, connection_name: str, all: bool = False, mount: Optional[str] = None
):
    from gefyra import api

    if not all and not name and not mount:
        console.error("Provide a name or use --all flag to unbridge.")
    if all:
        api.unbridge_all(connection_name=connection_name, wait=True)
    elif mount:
        deleted = api.delete_bridge(
            connection_name=connection_name,
            mount_name=mount,
            wait=False,
        )
        if deleted:
            console.success(f"GefyraBridge '{name}' marked for deletion")
    else:
        deleted = api.delete_bridge(
            connection_name=connection_name, name=name, wait=False
        )
        if deleted:
            console.success(f"GefyraBridge '{name}' marked for deletion")


@bridge.command(
    "list", alias=["ls"], help="List all GefyraBridges with local target containers"
)
@click.option(
    "-A",
    "--all",
    help="List all GefyraBridges from all GefyraClients",
    required=False,
    is_flag=True,
    default=False,
)
@click.pass_context
@standard_error_handler
def list_bridges(ctx, all):
    from gefyra import api

    bridges = api.list_bridges(
        kubeconfig=ctx.obj["kubeconfig"], kubecontext=ctx.obj["context"]
    )
    mounts = [[c.name, c._state, c.target, c.client, c.port_mappings] for c in bridges]
    if mounts:
        click.echo(
            tabulate(
                mounts,
                headers=["ID", "STATE", "BRIDGEMOUNT", "CLIENT", "PORT MAPPING"],
                tablefmt="plain",
            )
        )
    else:
        console.info("No GefyraBridges found")


@bridge.command(
    "inspect", alias=["describe", "show", "get"], help="Describe a GefyraBridge"
)
@click.argument("bridge_name")
@click.pass_context
@standard_error_handler
def inspect_bridge(ctx, bridge_name):
    from gefyra import api

    console.error("This CLI command is not yet implemented")

    # bridge_obj = api.get_bridge(
    #     bridge_name, kubeconfig=ctx.obj["kubeconfig"], kubecontext=ctx.obj["context"]
    # )
    # console.heading(bridge_obj.name)
    # console.info(f"uid: {bridge_obj.uid}")
    # console.info(f"States: {bridge_obj._state_transitions}")
    # console.heading("Events")
    # bridge_obj.watch_events(console.info, None, 1)
