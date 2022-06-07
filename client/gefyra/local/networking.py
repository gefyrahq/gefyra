import logging

from docker.errors import NotFound, APIError
from docker.models.networks import Network
from docker.types import IPAMConfig, IPAMPool

from gefyra.configuration import ClientConfiguration

logger = logging.getLogger(__name__)


def create_gefyra_network(config: ClientConfiguration) -> Network:
    gefyra_network = handle_create_network(config)
    logger.debug(f"Network {gefyra_network.attrs}")
    return gefyra_network


def handle_create_network(config: ClientConfiguration) -> Network:
    try:
        network = config.DOCKER.networks.get(config.NETWORK_NAME)
        logger.info("Gefyra network already exists")
        return network
    except NotFound:
        pass

    # this is a workaround to select a free subnet (instead of finding it with python code)
    temp_network = config.DOCKER.networks.create(config.NETWORK_NAME, driver="bridge")
    subnet = temp_network.attrs["IPAM"]["Config"][0]["Subnet"]
    temp_network.remove()  # remove the temp network again

    ipam_pool = IPAMPool(subnet=f"{subnet}", aux_addresses={})
    ipam_config = IPAMConfig(pool_configs=[ipam_pool])
    network = config.DOCKER.networks.create(
        config.NETWORK_NAME, driver="bridge", ipam=ipam_config
    )
    logger.info(f"Created network '{config.NETWORK_NAME}' ({network.short_id})")
    return network


def handle_remove_network(config: ClientConfiguration) -> None:
    """Removes all docker networks with the given name."""
    # we would need the id to identify the network unambiguously, so we just remove all networks that can be found with
    # the given name, under the assumption that no other docker network inadvertently uses the same name
    try:
        gefyra_network = config.DOCKER.networks.get(config.NETWORK_NAME)
        gefyra_network.remove()
    except NotFound:
        pass
    except APIError as e:
        logger.error(f"Could not remove network due to the following error: {e}")


def kill_remainder_container_in_network(
    config: ClientConfiguration, network_name
) -> None:
    """Kills all containers from this network"""
    try:
        network = config.DOCKER.networks.get(network_name)
        containers = network.attrs["Containers"].keys()
        for container in containers:
            c = config.DOCKER.containers.get(container)
            c.kill()
    except NotFound:
        pass
