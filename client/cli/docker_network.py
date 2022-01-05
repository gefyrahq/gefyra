import logging
import os
import sys

import docker

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.INFO)

NETWORK_NAME = os.getenv("GEFYRA_NETWORK_NAME", "gefyra_bridge")

client = docker.from_env()


def handle_create_network(name=NETWORK_NAME):
    # TODO this creates a network even if it already exists
    network = client.networks.create(name, driver="bridge")
    logger.info(f"Created docker network '{name}' ({network.short_id})")


def handle_remove_network(name=NETWORK_NAME):
    """Removes all docker networks with the given name."""
    # we would need the id to identify the network unambiguously, so we just remove all networks that can be found with
    # the given name, under the assumption that no other docker network inadvertently uses the same name
    networks = client.networks.list(name)
    for network in networks:
        network.remove()
    logger.info(f"Removed {len(networks)} docker networks with name '{name}'")
