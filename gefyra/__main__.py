#!/usr/bin/env python3
import argparse
import logging
import sys

from gefyra.api import down, up
from gefyra.local.bridge import bridge, run

console = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
console.setFormatter(formatter)

logger = logging.getLogger("gefyra")


parser = argparse.ArgumentParser(description="Gefyra Client")
parser.add_argument("action", help="One of: [up, run, bridge, reset, down]")
parser.add_argument("-v", "--verbose", action="store_true")
# the name will be used as an optional argument ("--name")
intercept_flags = [
    {"name": "app_image"},
    {"name": "destination_ip"},
    {"name": "destination_port"},
    {"name": "target_pod"},
    {"name": "target_container"},
    {"name": "target_container_port"},
    {"name": "target_namespace"},
]
for flag in intercept_flags:
    parser.add_argument(f"--{flag['name']}")


def get_intercept_kwargs(parser_args):
    kwargs = {}
    for flag in intercept_flags:
        if getattr(parser_args, flag["name"]):
            kwargs[flag["name"]] = getattr(parser_args, flag["name"])
    return kwargs


if __name__ == "__main__":
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    logger.addHandler(console)
    if args.action == "up":
        up()
    elif args.action == "run":
        logger.info("run: gonna call run")
        run(**get_intercept_kwargs(args))
        logger.info("run: run called")
    elif args.action == "bridge":
        logger.info("bridge: gonna call bridge")
        bridge(**get_intercept_kwargs(args))
        logger.info("bridge: bridge called")
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
