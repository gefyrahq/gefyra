import logging
from typing import TYPE_CHECKING, List, Optional


from gefyra.configuration import ClientConfiguration
from gefyra.local import CREATED_BY_LABEL

if TYPE_CHECKING:
    from docker.models.networks import Network


logger = logging.getLogger(__name__)


def get_or_create_gefyra_network(
    config: ClientConfiguration, occupied_networks: Optional[List[str]] = None
) -> "Network":
    if not occupied_networks:
        occupied_networks = []
    gefyra_network = handle_create_network(config, occupied_networks)
    logger.debug(f"Network {gefyra_network.attrs}")
    return gefyra_network


def _get_subnet(
    config: ClientConfiguration, network_name: str, occupied_networks: List[str]
) -> str:
    tries = 255
    networks: List[Network] = []
    subnet = ""
    # this is a workaround to select a free subnet (instead of finding it with python code)
    for i in range(tries):
        temp_network = config.DOCKER.networks.create(
            f"{network_name}-{i}", driver="bridge"
        )
        networks.append(temp_network)
        subnet = temp_network.attrs["IPAM"]["Config"][0]["Subnet"]
        if subnet not in occupied_networks:
            break
    for network in networks:
        network.remove()
    if not subnet:
        raise RuntimeError("Could not find a free subnet")
    return subnet


def handle_create_network(
    config: ClientConfiguration, occupied_networks: List[str]
) -> "Network":
    from docker.errors import NotFound
    from docker.types import IPAMConfig, IPAMPool

    DOCKER_MTU_OPTION = "com.docker.network.driver.mtu"
    network_name = f"{config.NETWORK_NAME}"
    try:
        network = config.DOCKER.networks.get(network_name)
        logger.info("Gefyra network already exists")
        if (
            CREATED_BY_LABEL[0] not in network.attrs["Labels"]
            or network.attrs["Labels"][CREATED_BY_LABEL[0]] != "true"
        ):
            logger.debug(f"Docker network '{network.name}' is not managed by Gefyra")
        if (
            "Options" in network.attrs
            and DOCKER_MTU_OPTION in network.attrs["Options"]
            and network.attrs["Options"][DOCKER_MTU_OPTION] != config.WIREGUARD_MTU
        ) or (
            "Options" in network.attrs
            and DOCKER_MTU_OPTION not in network.attrs["Options"]
        ):
            _mtu = (
                network.attrs["Options"].get(DOCKER_MTU_OPTION)
                if "Options" in network.attrs
                else "default"
            )
            logger.warning(
                f"The MTU value of the '{network_name}' network (={_mtu}) is different"
                f" from the --wireguard-mtu parameter (={config.WIREGUARD_MTU}) or"
                " default. You may experience bad network connections. Consider"
                f" removing the network '{network_name}' with 'docker network rm"
                f" {network_name}' before running setting up Gefyra."
            )
        return network
    except NotFound:
        pass

    subnet = _get_subnet(
        config=config, network_name=network_name, occupied_networks=occupied_networks
    )
    logger.debug(f"Using subnet: {subnet}")

    ipam_pool = IPAMPool(subnet=f"{subnet}", aux_addresses={})
    ipam_config = IPAMConfig(pool_configs=[ipam_pool])
    network = config.DOCKER.networks.create(
        network_name,
        driver="bridge",
        ipam=ipam_config,
        labels={
            CREATED_BY_LABEL[0]: CREATED_BY_LABEL[1],
        },
        options={DOCKER_MTU_OPTION: config.WIREGUARD_MTU},
    )
    logger.info(f"Created network '{network_name}' ({network.short_id})")
    return network


def handle_remove_network(config: ClientConfiguration) -> None:
    """Removes all docker networks with the given name."""
    # we would need the id to identify the network unambiguously, so we just remove all networks that can be found with
    # the given name, under the assumption that no other docker network inadvertently uses the same name
    from docker.errors import NotFound, APIError

    kill_remainder_container_in_network(config=config)
    try:
        gefyra_network = config.DOCKER.networks.get(f"{config.NETWORK_NAME}")
        if (
            CREATED_BY_LABEL[0] in gefyra_network.attrs["Labels"]
            and gefyra_network.attrs["Labels"][CREATED_BY_LABEL[0]] == "true"
        ):
            logger.info(f"Removing Docker network {gefyra_network.name}")
            gefyra_network.remove()
        else:
            logger.info(
                f"Docker network {gefyra_network.name} is not managed by Gefyra"
            )
    except NotFound:
        pass
    except APIError as e:
        logger.error(f"Could not remove network due to the following error: {e}")


def kill_remainder_container_in_network(config: ClientConfiguration) -> None:
    """Kills all containers from this network"""
    from docker.errors import NotFound

    try:
        network = config.DOCKER.networks.get(f"{config.NETWORK_NAME}")
        containers = network.attrs["Containers"].keys()
        for container in containers:
            c = config.DOCKER.containers.get(container)
            if (
                CREATED_BY_LABEL[0] in c.attrs["Config"]["Labels"]
                and c.attrs["Config"]["Labels"][CREATED_BY_LABEL[0]] == "true"
            ):
                c.kill()
    except NotFound:
        pass
