#!/usr/bin/env python3
import argparse
import logging

from .operator.install_operator import install_operator
from .operator.uninstall_operator import uninstall_operator

logger = logging.getLogger(__name__)


parser = argparse.ArgumentParser(description="Gefyra Client")
parser.add_argument("action", help="One of: [init, run, intercept, shutdown]")


if __name__ == "__main__":
    args = parser.parse_args()
    if args.action == "init":
        logger.info("init: gonna install operator")
        install_operator()
        logger.info("init: operator installed")
    elif args.action == "shutdown":
        logger.info("shutdown: gonna uninstall operator")
        uninstall_operator()
        logger.info("shutdown: operator uninstalled")
    else:
        print("Not yet supported")
