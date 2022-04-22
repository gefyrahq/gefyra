import json
import logging

from gefyra.configuration import default_configuration


from . import down

logger = logging.getLogger(__name__)


def up(cargo_endpoint: str = None, config=default_configuration) -> bool:
    from kubernetes.client import ApiException
    from gefyra.cluster.manager import install_operator
    from gefyra.local.cargo import create_cargo_container, get_cargo_ip_from_netaddress
    from gefyra.local.networking import (
        get_free_class_c_netaddress,
        handle_create_network,
    )
    from docker.errors import APIError

    if cargo_endpoint:
        config.CARGO_ENDPOINT = cargo_endpoint
    logger.info("Installing Gefyra Operator")
    #
    # Deploy Operator to cluster, aligned with local conditions
    #
    try:
        logger.debug("Creating Docker network")
        network_address = get_free_class_c_netaddress(config)
        gefyra_network = handle_create_network(config, network_address, {})
        logger.debug(f"Network {gefyra_network.attrs}")
        cargo_connection_details = install_operator(
            config, gefyra_network.attrs["IPAM"]["Config"][0]["Subnet"]
        )
    except ApiException as e:
        data = json.loads(e.body)
        try:
            logger.error(f"{e.reason}: {data['details']['causes'][0]['message']}")
        except KeyError:
            logger.error(f"{e.reason}: {data}")

        return False
    #
    # Run up a local Docker network setup
    #
    try:
        cargo_com_net_ip_address = cargo_connection_details["Interface.Address"]
        stowaway_ip_address = cargo_connection_details["Interface.DNS"].split(" ")[0]
        logger.debug(f"Cargo com net ip address: {cargo_com_net_ip_address}")
        logger.debug(f"Stowaway com net ip address: {stowaway_ip_address}")
        # well known cargo address
        logger.debug(gefyra_network.attrs)
        cargo_ip_address = get_cargo_ip_from_netaddress(
            gefyra_network.attrs["IPAM"]["Config"][0]["Subnet"]
        )
        logger.info(f"Deploying Cargo (network sidecar) with IP {cargo_ip_address}")
    except Exception as e:
        logger.error(e)
        down(config)
        return False
    #
    # Connect Docker network with K8s cluster
    #
    try:
        cargo_container = create_cargo_container(config, cargo_connection_details)
        logger.debug(f"Cargo gefyra net ip address: {cargo_ip_address}")
        gefyra_network.connect(cargo_container, ipv4_address=cargo_ip_address)
        cargo_container.start()
    except APIError as e:
        if e.status_code == 409:
            logger.warning("Cargo is already deployed and running")
        else:
            raise e
    return True
