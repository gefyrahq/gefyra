import json
import logging

import docker
import kubernetes as k8s

from gefyra.cluster.manager import install_operator
from gefyra.configuration import default_configuration
from gefyra.local.cargo import create_cargo_container
from gefyra.local.networking import handle_create_network

from .utils import stopwatch

logger = logging.getLogger(__name__)


@stopwatch
def up(config=default_configuration) -> bool:
    logger.info("Installing Gefyra Operator")
    # TODO handle cluster unready errors (e.g. namespace terminating)
    try:
        cargo_connection_details = install_operator(config)
    except k8s.client.exceptions.ApiException as e:
        data = json.loads(e.body)
        logger.error(f"{e.reason}: {data['details']['causes']}")
        return False

    stowaway_ip_octets = list(
        map(int, cargo_connection_details["Interface.Address"].split("."))
    )
    network_address = (
        f"{stowaway_ip_octets[0]}.{stowaway_ip_octets[1]}." f"{stowaway_ip_octets[2]}.0"
    )
    cargo_ip_address = (
        f"{stowaway_ip_octets[0]}.{stowaway_ip_octets[1]}."
        f"{stowaway_ip_octets[2]}.{stowaway_ip_octets[3] + 1}"
    )
    logger.debug(f"Cargo ip address: {cargo_ip_address}")
    logger.debug(f"Gefyra network address: {network_address}")
    logger.info("Creating Docker network")
    gefyra_network = handle_create_network(config, network_address, cargo_ip_address)
    logger.info("Deploying Cargo (network sidecar)")

    try:
        cargo_container = create_cargo_container(config, cargo_connection_details)
        gefyra_network.connect(cargo_container, ipv4_address=cargo_ip_address)
    except docker.errors.APIError as e:
        if e.status_code == 409:
            logger.warning("Cargo is already deployed and running")
        else:
            raise e
    return True
