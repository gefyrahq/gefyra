#!/usr/bin/env python3
import argparse
import logging
import sys

from cli.docker_network import handle_create_network, handle_remove_network

from .operator.install_operator import install_operator
from .operator.uninstall_operator import uninstall_operator

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.INFO)


parser = argparse.ArgumentParser(description="Gefyra Client")
parser.add_argument("action", help="One of: [init, run, bridge, reset, shutdown]")


if __name__ == "__main__":
    args = parser.parse_args()
    if args.action == "init":
        logger.info("init: gonna install operator")
        install_operator()
        logger.info("init: operator installed")
        logger.info("init: gonna create docker network")
        handle_create_network()
        logger.info("init: created docker network")
    elif args.action == "run":
        logger.warning("run: not yet supported")
    elif args.action == "bridge":
        logger.warning("bridge: not yet supported")
    elif args.action == "reset":
        logger.warning("reset: not yet supported")
    elif args.action == "shutdown":
        logger.info("shutdown: gonna uninstall operator")
        uninstall_operator()
        logger.info("shutdown: operator uninstalled")
        logger.info("shutdown: gonna remove docker network")
        handle_remove_network()
        logger.info("shutdown: removed docker network")
    else:
        logger.error(
            f"action must be one of [init, run, bridge, shutdown], got {args.action}"
        )
