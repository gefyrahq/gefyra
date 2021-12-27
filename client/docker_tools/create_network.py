import logging
import os

import docker

logger = logging.getLogger(__name__)

NETWORK_NAME = os.getenv("GEFYRA_NETWORK_NAME", "gefyra_bridge")

client = docker.from_env()


def handle_create_network(name=NETWORK_NAME):
    client.networks.create(name, driver="bridge")
    logger.info(f"Create docker network '{name}'")
