#!/usr/bin/env python3
import argparse
import logging
import sys

from .cli.bridge import bridge, run
from .operator.install_operator import install_operator
from .operator.uninstall_operator import uninstall_operator

# from .cli.docker_network import handle_create_network, handle_remove_network


logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.INFO)


parser = argparse.ArgumentParser(description="Gefyra Client")
parser.add_argument("action", help="One of: [init, run, bridge, reset, shutdown]")
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
    if args.action == "init":
        logger.info("init: gonna install operator")
        install_operator()
        logger.info("init: operator installed")
        # logger.info("init: gonna create docker network")
        # handle_create_network()
        # logger.info("init: created docker network")
    elif args.action == "run":
        logger.info("run: gonna call run")
        run(**get_intercept_kwargs(args))
        logger.info("run: run called")
    elif args.action == "bridge":
        logger.info("bridge: gonna call bridge")
        bridge(**get_intercept_kwargs(args))
        logger.info("bridge: bridge called")
    elif args.action == "reset":
        # idea: to delete one ireq (reset may not be the best name for that, choices menu like in unikube would be nice)
        logger.warning("reset: not yet supported")
    elif args.action == "shutdown":
        logger.info("shutdown: gonna uninstall operator")
        uninstall_operator()
        logger.info("shutdown: operator uninstalled")
        # logger.info("shutdown: gonna remove docker network")
        # handle_remove_network()
        # logger.info("shutdown: removed docker network")
    else:
        logger.error(
            f"action must be one of [init, run, bridge, shutdown], got {args.action}"
        )
