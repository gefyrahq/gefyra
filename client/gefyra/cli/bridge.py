import dataclasses
import os
from time import sleep
from typing import List, Optional
from alive_progress import alive_bar
import click
from gefyra.local.bridge import get_all_containers
from gefyra.types import ExactMatchHeader
from gefyra.cli import console
from gefyra.cli.utils import (
    AliasedGroup,
    check_connection_name,
    parse_ip_port_map,
    parse_match_header,
    parse_match_path,
    standard_error_handler,
)
from gefyra.types.bridge import (
    ExactMatchPath,
    GefyraBridge,
    PrefixMatchHeader,
    PrefixMatchPath,
    RegexMatchHeader,
    RegexMatchPath,
)
from tabulate import tabulate


@click.group(
    "bridge",
    cls=AliasedGroup,
    help="Manage your GefyraBridges to redirect traffic from a GefyraBridgeMount target",
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
    "-t",
    "--local",
    "--target",
    help="The name of the local container running in Gefyra",
    required=True,
)
@click.option(
    "-N",
    "--name",
    help="Assign a custom name to this GefyraBridge",
    required=False,
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
    "--match-header-exact",
    help="Match header exactly to forward traffic to this client. E.g.: --match-header-exact x-gefyra:peer",
    required=False,
    multiple=True,
    callback=parse_match_header,
)
@click.option(
    "--match-header-regex",
    help="Match header regex expression to forward traffic to this client. E.g.: --match-header-regex x-gefyra:(.*))",
    required=False,
    multiple=True,
    callback=parse_match_header,
)
@click.option(
    "--match-header-prefix",
    help="Match header value prefix (and name exactly) to forward traffic to this client. E.g.: --match-header-prefix x-gefyra:peer1,",
    required=False,
    multiple=True,
    callback=parse_match_header,
)
@click.option(
    "--match-path-prefix",
    help="Match path prefix to forward traffic to this client. E.g.: --match-path-prefix myroute/",
    required=False,
    multiple=True,
    callback=parse_match_path,
)
@click.option(
    "--match-path-regex",
    help="Match patch regex to forward traffic to this client. E.g.: --match-path-regex myroute/(.*)/all",
    required=False,
    multiple=True,
    callback=parse_match_path,
)
@click.option(
    "--match-path-exact",
    help="Match path exactly to forward traffic to this client. E.g.: --match-path-exact /only/this",
    required=False,
    multiple=True,
    callback=parse_match_path,
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
    local,
    ports,
    mount,
    match_header_exact: List[ExactMatchHeader],
    match_header_prefix: List[PrefixMatchHeader],
    match_header_regex: List[RegexMatchHeader],
    match_path_exact: List[ExactMatchPath],
    match_path_prefix: List[PrefixMatchPath],
    match_path_regex: List[RegexMatchPath],
    no_probe_handling,
    connection_name,
    nowait,
    timeout,
):
    from gefyra import api

    rules = [
        match_header_exact,
        match_header_regex,
        match_header_prefix,
        match_path_exact,
        match_path_prefix,
        match_path_regex,
    ]
    if not any(rules):
        raise click.MissingParameter(
            "You have to pass at least one rule to match traffic in the target GefyraBridgeMount"
        )

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
            local=local,
            ports=ports,
            bridge_mount_name=mount,
            connection_name=connection_name,
            rules=rules,
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
@click.option("--connection-name", type=str, default="default")
@click.pass_context
@standard_error_handler
def list_bridges(ctx, all: bool, connection_name: str):
    from gefyra import api

    if not all and connection_name:
        check_connection_name(None, None, connection_name)
        bridges = api.list_bridges(
            kubeconfig=ctx.obj["kubeconfig"],
            kubecontext=ctx.obj["context"],
            connection_name=connection_name,
            filter_client=True,
            get_containers=True,
        )
        bridges = [
            [
                b.name,
                b._state,
                b.target,
                b.port_mappings,
                c.short_id if c else "-",
                c.name if c else "-",
            ]
            for c, b in bridges
        ]
        if bridges:
            click.echo(
                tabulate(
                    bridges,
                    headers=[
                        "ID",
                        "STATE",
                        "BRIDGEMOUNT",
                        "PORT MAPPING",
                        "TARGET CONTAINER",
                        "TARGET CONTAINER NAME",
                    ],
                    tablefmt="plain",
                )
            )
        else:
            console.info("No GefyraBridges found")
    else:
        bridges = api.list_bridges(
            kubeconfig=ctx.obj["kubeconfig"],
            kubecontext=ctx.obj["context"],
            filter_client=False,
        )
        bridges = [
            [c.name, c._state, c.target, c.client, c.port_mappings] for c in bridges
        ]
        if bridges:
            click.echo(
                tabulate(
                    bridges,
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

    # TODO add connection-name support
    bridge_obj = api.get_bridge(
        bridge_name, kubeconfig=ctx.obj["kubeconfig"], kubecontext=ctx.obj["context"]
    )
    console.heading(bridge_obj.name)
    console.info(f"States: {bridge_obj._state_transitions}")
    console.info(f"GefyraBridgeMount: {bridge_obj.target}")
    console.info(f"Provider Parameters: {bridge_obj.rules}")
    console.heading("Events")
    bridge_obj.watch_events(console.info, None, 1)
