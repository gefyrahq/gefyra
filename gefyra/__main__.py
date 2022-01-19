#!/usr/bin/env python3
import argparse
import logging
import sys

from gefyra.api import bridge, down, run, up

console = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("[%(levelname)s] %(name)s %(message)s")
console.setFormatter(formatter)

logger = logging.getLogger("gefyra")


parser = argparse.ArgumentParser(description="Gefyra Client")
action = parser.add_subparsers(dest="action", help="the action to be performed")
parser.add_argument("-d", "--debug", action="store_true", help="add debug output")

up_parser = action.add_parser("up")
run_parser = action.add_parser("run")
run_parser.add_argument(
    "-i", "--image", help="the docker image to run locally", required=True
)
run_parser.add_argument(
    "-N", "--name", help="the name for the locally running container", required=True
)
run_parser.add_argument(
    "-n",
    "--namespace",
    help="the namespace for this container to run in",
    default="default",
)
bridge_parser = action.add_parser("bridge")
bridge_parser.add_argument(
    "-N", "--name", help="the name for the locally running container", required=True
)
bridge_parser.add_argument(
    "-p", "--port", help="the port to send the traffic to", required=True
)
bridge_parser.add_argument(
    "-n",
    "--namespace",
    help="the namespace for this container to run in",
    default="default",
)
intercept_flags = [
    {"name": "deployment"},
    {"name": "statefulset"},
    {"name": "pod"},
    {"name": "container_name"},
    {"name": "container_port"},
    #    {"name": "namespace"}, target namespace
]
for flag in intercept_flags:
    bridge_parser.add_argument(f"--{flag['name']}")

down_parser = action.add_parser("down")


def get_intercept_kwargs(parser_args):
    kwargs = {}
    for flag in intercept_flags:
        if getattr(parser_args, flag["name"]):
            kwargs[flag["name"]] = getattr(parser_args, flag["name"])
    return kwargs


if __name__ == "__main__":
    args = parser.parse_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    logger.addHandler(console)
    if args.action == "up":
        up()
    elif args.action == "run":
        run(image=args.image, name=args.name, namespace=args.namespace)
    elif args.action == "bridge":
        bridge(args.name, args.port, **get_intercept_kwargs(args))
    elif args.action == "reset":
        # idea: to delete one/all ireqs (reset may not be the best name for that, choices menu like in unikube would be
        # nice)
        logger.warning("reset: not yet supported")
    elif args.action == "down":
        down()
    else:
        logger.error(
            f"action must be one of [up, run, bridge, down], got {args.action}"
        )
