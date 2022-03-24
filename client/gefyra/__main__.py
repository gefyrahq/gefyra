#!/usr/bin/env python3
import argparse
import logging

logger = logging.getLogger("gefyra")
parser = argparse.ArgumentParser(
    prog="gefyra",
    description="The Gefyra client. For more help please visit: https://gefyra.dev",
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


def get_intercept_kwargs(parser_args):
    kwargs = {}
    for flag in intercept_flags:
        _f = flag["name"].replace("-", "_")
        if getattr(parser_args, _f):
            kwargs[_f] = getattr(parser_args, _f)
    return kwargs


def main():
    from gefyra import configuration
    from gefyra.api import (
        bridge,
        down,
        run,
        up,
        unbridge,
        unbridge_all,
        list_interceptrequests,
    )
    from gefyra.local.check import probe_kubernetes, probe_docker

    args = parser.parse_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    logger.addHandler(configuration.console)
    if args.action == "up":
        up(cargo_endpoint=args.endpoint)
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
    elif args.action == "list":
        if args.containers:
            pass
        elif args.bridges:
            ireqs = list_interceptrequests()
            if ireqs:
                for ireq in ireqs:
                    print(ireq)
            else:
                logger.info("No active bridges found")
    elif args.action == "down":
        down()
    elif args.action == "check":
        probe_docker()
        probe_kubernetes()
    elif args.action == "version":
        logger.info(f"Gefyra client version: {configuration.__VERSION__}")
    else:
        parser.print_help()


if __name__ == "__main__":  # noqa
    try:
        main()
        exit(0)
    except Exception as e:
        logger.fatal(f"There was an error running Gefyra: {e}")
        exit(1)
