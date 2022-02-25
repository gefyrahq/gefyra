import logging
from random import choice

from docker.errors import NotFound
from docker.models.networks import Network
from docker.types import IPAMConfig, IPAMPool

from gefyra.configuration import ClientConfiguration

logger = logging.getLogger(__name__)


def handle_create_network(
    config: ClientConfiguration, network_address: str, aux_addresses: dict
) -> Network:
    try:
        network = config.DOCKER.networks.get(config.NETWORK_NAME)
        logger.info("Gefyra network already exists")
        return network
    except NotFound:
        pass
    ipam_pool = IPAMPool(subnet=f"{network_address}/24", aux_addresses=aux_addresses)
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
    networks = config.DOCKER.networks.list(config.NETWORK_NAME)
    for network in networks:
        network.remove()
    logger.info(
        f"Removed {len(networks)} docker networks with name '{config.NETWORK_NAME}'"
    )


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


def get_free_class_c_netaddress(config: ClientConfiguration):
    taken_netaddress = []
    for network in config.DOCKER.networks.list():
        try:
            config_list = network.attrs["IPAM"]["Config"]
            for config in config_list:
                taken_netaddress.append(config["Subnet"])
        except KeyError:
            continue
    class_c = filter(lambda s: s.startswith("192.168."), taken_netaddress)
    exc_tho = [int(o.split(".")[2]) for o in class_c]
    tho = choice([i for i in range(10, 200) if i not in exc_tho])
    return f"192.168.{tho}.0"
