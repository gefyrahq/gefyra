import json
import logging

import docker
import kubernetes as k8s

from gefyra.cluster.manager import install_operator
from gefyra.configuration import default_configuration
from gefyra.local.cargo import create_cargo_container, get_cargo_ip_from_netaddress
from gefyra.local.networking import get_free_class_c_netaddress, handle_create_network

from . import down
from .utils import stopwatch

logger = logging.getLogger(__name__)


@stopwatch
def up(config=default_configuration) -> bool:
    logger.info("Installing Gefyra Operator")
    #
    # Deploy Operator to cluster, aligned with local conditions
    #
    try:
        network_address = get_free_class_c_netaddress(config)
        cargo_connection_details = install_operator(config, network_address)
    except k8s.client.exceptions.ApiException as e:
        data = json.loads(e.body)
        logger.error(f"{e.reason}: {data['details']['causes'][0]['message']}")
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
        cargo_ip_address = get_cargo_ip_from_netaddress(network_address)
        logger.debug(f"Gefyra network address: {network_address}")
        logger.info("Creating Docker network")
        gefyra_network = handle_create_network(config, network_address, {})
        logger.info("Deploying Cargo (network sidecar)")
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
    except docker.errors.APIError as e:
        if e.status_code == 409:
            logger.warning("Cargo is already deployed and running")
        else:
            raise e
    return True
