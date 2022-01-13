import logging

from docker.models.networks import Network

from gefyra.configuration import ClientConfiguration

logger = logging.getLogger(__name__)


def handle_create_network(config: ClientConfiguration, network_address: str, gateway_address: str) -> Network:
    network = config.DOCKER.networks.get(config.NETWORK_NAME)
    if network:
        logger.warning("Docker network already exists")
        return network
    else:
        ipam_pool = config.DOCKER.types.IPAMPool(subnet=f"{network_address}/24", gateway=gateway_address)
        ipam_config = config.DOCKER.types.IPAMConfig(pool_configs=[ipam_pool])
        network = config.DOCKER.networks.create(config.NETWORK_NAME, driver="bridge", ipam=ipam_config)
        logger.info(f"Created docker network '{config.NETWORK_NAME}' ({network.short_id})")
        return network


def handle_remove_network(config: ClientConfiguration) -> None:
    """Removes all docker networks with the given name."""
    # we would need the id to identify the network unambiguously, so we just remove all networks that can be found with
    # the given name, under the assumption that no other docker network inadvertently uses the same name
    networks = config.DOCKER.networks.list(config.NETWORK_NAME)
    for network in networks:
        network.remove()
    logger.info(f"Removed {len(networks)} docker networks with name '{config.NETWORK_NAME}'")
