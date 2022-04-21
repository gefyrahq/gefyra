import json
import logging
from typing import Any

from gefyra.configuration import default_configuration


from . import down

logger = logging.getLogger(__name__)


def set_image_urls(
    operator_image_url: str = None,
    stowaway_image_url: str = None,
    carrier_image_url: str = None,
    cargo_image_url: str = None,
    registry_url: str = None,
    config: Any
):
    if operator_image_url:
        config.OPERATOR_IMAGE = operator_image_url
    if stowaway_image_url:
        config.STOWAWAY_IMAGE = stowaway_image_url
    if carrier_image_url:
        config.CARRIER_IMAGE = carrier_image_url
    if cargo_image_url:
        config.CARGO_IMAGE = cargo_image_url
    if registry_url:
        config.REGISTRY_URL = registry_url


def up(
        cargo_endpoint: str = None,
        config=default_configuration,
        operator_image_url: str = None,
        stowaway_image_url: str = None,
        carrier_image_url: str = None,
        cargo_image_url: str = None,
        registry_url: str = None,
) -> bool:
    from kubernetes.client import ApiException
    from gefyra.cluster.manager import install_operator
    from gefyra.local.cargo import create_cargo_container, get_cargo_ip_from_netaddress
    from gefyra.local.networking import (
        get_free_class_c_netaddress,
        handle_create_network,
    )
    from docker.errors import APIError

    set_image_urls(
        operator_image_url=operator_image_url,
        stowaway_image_url=stowaway_image_url,
        carrier_image_url=carrier_image_url,
        cargo_image_url=cargo_image_url,
        registry_url=registry_url,
        config=config,
    )

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
