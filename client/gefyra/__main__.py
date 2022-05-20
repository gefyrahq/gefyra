#!/usr/bin/env python3
import argparse
import logging

from gefyra.configuration import ClientConfiguration

logger = logging.getLogger("gefyra")
parser = argparse.ArgumentParser(
    prog="gefyra",
    description="The Gefyra client. For more help please visit: https://gefyra.dev/reference/cli/",
)
action = parser.add_subparsers(dest="action", help="the action to be performed")
parser.add_argument("-d", "--debug", action="store_true", help="add debug output")


up_parser = action.add_parser("up")
up_parser.add_argument(
    "-e",
    "--endpoint",
    help="the Wireguard endpoint in the form <IP>:<Port> for Gefyra to connect to",
    required=False,
)
up_parser.add_argument(
    "-o",
    "--operator",
    help="Registry url for the operator image.",
    required=False,
)
up_parser.add_argument(
    "-s",
    "--stowaway",
    help="Registry url for the stowaway image.",
    required=False,
)
up_parser.add_argument(
    "-c",
    "--carrier",
    help="Registry url for the carrier image.",
    required=False,
)
up_parser.add_argument(
    "-a",
    "--cargo",
    help="Registry url for the cargo image.",
    required=False,
)
up_parser.add_argument(
    "-r",
    "--registry",
    help="Base url for registry to pull images from.",
    required=False,
)
run_parser = action.add_parser("run")
run_parser.add_argument(
    "-i", "--image", help="the docker image to run in Gefyra", required=True
)
run_parser.add_argument(
    "-N", "--name", help="the name of the container running in Gefyra", required=True
)
run_parser.add_argument(
    "-c",
    "--command",
    help="the command for this container to in Gefyra",
    nargs="+",
    required=False,
)
run_parser.add_argument(
    "-n",
    "--namespace",
    help="the namespace for this container to run in",
    default="default",
)
run_parser.add_argument(
    "--env",
    action="append",
    help="set or override environment variables in the form ENV=value, allowed multiple times",
    required=False,
)
run_parser.add_argument(
    "-v",
    "--volume",
    action="append",
    help="Bind mount a volume into the container in notation src:dest, allowed multiple times",
    required=False,
)
run_parser.add_argument(
    "--env-from",
    help="copy the environment from the container in the notation 'Pod/Container'",
    required=False,
)
bridge_parser = action.add_parser("bridge")
bridge_parser.add_argument(
    "-N", "--name", help="the name of the container running in Gefyra", required=True
)
bridge_parser.add_argument(
    "-C",
    "--container-name",
    help="the name for the locally running container",
    required=True,
)
bridge_parser.add_argument(
    "-I", "--bridge-name", help="the name of the bridge", required=False
)
bridge_parser.add_argument(
    "-p", "--port", help="the port mapping", required=True, action="append"
)
bridge_parser.add_argument(
    "-n",
    "--namespace",
    help="the namespace for this container to run in",
    default="default",
)
bridge_parser.add_argument(
    "-P",
    "--no-probe-handling",
    action="store_true",
    help="make Carrier to not handle probes during switch operation",
    default=False,
)
intercept_flags = [
    {"name": "deployment"},
    {"name": "statefulset"},
    {"name": "pod"},
    {"name": "container"},
]
for flag in intercept_flags:
    bridge_parser.add_argument(f"--{flag['name']}")

unbridge_parser = action.add_parser("unbridge")
unbridge_parser.add_argument("-N", "--name", help="the name of the bridge")
unbridge_parser.add_argument(
    "-A", "--all", help="removes all active bridges", action="store_true"
)
list_parser = action.add_parser("list")
list_parser.add_argument(
    "--containers", help="list all containers running in Gefyra", action="store_true"
)
list_parser.add_argument(
    "--bridges", help="list all active bridges in Gefyra", action="store_true"
)
down_parser = action.add_parser("down")
check_parser = action.add_parser("check")
version_parser = action.add_parser("version")

version_parser.add_argument(
    "-n",
    "--no-check",
    help="Do not check whether there is a new version",
    action="store_true",
    default=False,
)


def get_intercept_kwargs(parser_args):
    kwargs = {}
    for flag in intercept_flags:
        _f = flag["name"].replace("-", "_")
        if getattr(parser_args, _f):
            kwargs[_f] = getattr(parser_args, _f)
    return kwargs


def up_command(args):
    from gefyra.api import up

    configuration = ClientConfiguration(
        cargo_endpoint=args.endpoint,
        registry_url=args.registry,
        operator_image_url=args.operator,
        stowaway_image_url=args.stowaway,
        cargo_image_url=args.cargo,
        carrier_image_url=args.carrier,
    )

    up(config=configuration)


def get_containers_and_print():
    from gefyra.api import list_containers

    containers = list_containers()
    containers.insert(0, ("NAME", "IP_ADDRESS"))
    for name, ip in containers:
        print("{:<30}{}".format(name, ip))


def get_bridges_and_print():
    from gefyra.api import list_interceptrequests

    ireqs = list_interceptrequests()
    if ireqs:
        for ireq in ireqs:
            print(ireq)
    else:
        logger.info("No active bridges found")


def version(config, check: bool):
    import requests

    logger.info(f"Gefyra client version: {config.__VERSION__}")
    if check:
        release = requests.get(
            "https://api.github.com/repos/gefyrahq/gefyra/releases/latest"
        )
        if release.status_code == 403:
            logger.info("Versions cannot be compared, as API rate limit was exceeded")
            return None
        latest_release_version = release.json()["tag_name"].replace("-", ".")
        if config.__VERSION__ != latest_release_version:
            logger.info(
                f"You are using gefyra version {config.__VERSION__}; however, version {latest_release_version} is "
                f"available."
            )


def main():
    try:
        from gefyra import configuration
        from gefyra.api import (
            bridge,
            down,
            run,
            unbridge,
            unbridge_all,
        )
        from gefyra.local.check import probe_kubernetes, probe_docker

        args = parser.parse_args()
        if args.debug:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
        logger.addHandler(configuration.console)
        if args.action == "up":
            up_command(args)
        elif args.action == "run":
            run(
                image=args.image,
                name=args.name,
                command=" ".join(args.command) if args.command else None,
                namespace=args.namespace,
                env_from=args.env_from,
                env=args.env,
                volumes=args.volume,
            )
        elif args.action == "bridge":
            bridge(
                args.name,
                args.port,
                container_name=args.container_name,
                namespace=args.namespace,
                bridge_name=args.bridge_name,
                handle_probes=not args.no_probe_handling,
                **get_intercept_kwargs(args),
            )
        elif args.action == "unbridge":
            if args.name:
                unbridge(args.name)
            elif args.all:
                unbridge_all()
            else:
                logger.warning(
                    "Unbridge failed. Please use command with either -N or -A flag."
                )
        elif args.action == "list":
            if args.containers:
                get_containers_and_print()
            elif args.bridges:
                get_bridges_and_print()
        elif args.action == "down":
            down()
        elif args.action == "check":
            probe_docker()
            probe_kubernetes()
        elif args.action == "version":
            check = not args.no_check
            version(configuration, check)
        else:
            parser.print_help()
    except Exception as e:
        logger.fatal(f"There was an error running Gefyra: {e}")
        exit(1)
    exit(0)


if __name__ == "__main__":  # noqa
    main()
