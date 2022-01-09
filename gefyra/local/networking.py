import logging

from gefyra.configuration import ClientConfiguration

logger = logging.getLogger(__name__)


def handle_create_network(config: ClientConfiguration) -> None:
    # TODO this creates a network even if it already exists
    networks = config.DOCKER.networks.list(config.NETWORK_NAME)
    if networks:
        logger.warning("Docker network already exists")
    else:
        network = config.DOCKER.networks.create(config.NETWORK_NAME, driver="bridge")
        logger.info(
            f"Created docker network '{config.NETWORK_NAME}' ({network.short_id})"
        )


def handle_remove_network(config: ClientConfiguration) -> None:
    """Removes all docker networks with the given name."""
    # we would need the id to identify the network unambiguously, so we just remove all networks that can be found with
    # the given name, under the assumption that no other docker network inadvertently uses the same name
    networks = config.DOCKER.networks.list(config.NETWORK_NAME)
    for network in networks:
        network.remove()
    logger.info(
        f"Removed {len(networks)} docker networks with name '{config.NETWORK_NAME}'"
    )
