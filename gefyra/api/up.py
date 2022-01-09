import json
import logging

import docker
import kubernetes as k8s

from gefyra.cluster.manager import install_operator
from gefyra.configuration import default_configuration
from gefyra.local.cargo import deploy_cargo_container
from gefyra.local.networking import handle_create_network
from gefyra.local.utils import get_container_ip

from .utils import stopwatch

logger = logging.getLogger(__name__)


@stopwatch
def up(config=default_configuration) -> bool:
    logger.info("Installing Gefyra Operator")
    # TODO handle cluster unready errors (e.g. namespace terminating)
    try:
        install_operator(config)
    except k8s.client.exceptions.ApiException as e:
        data = json.loads(e.body)
        logger.error(f"{e.reason}: {data['details']['causes']}")
        return False

    logger.info("Creating Docker network")
    handle_create_network(config)
    logger.info("Deploying Cargo (network sidecar)")
    try:
        cargo_container = deploy_cargo_container(config)
        cargo_ip = get_container_ip(config, container=cargo_container)
        logger.debug(f"Cargo IP is: {cargo_ip}")
    except docker.errors.APIError as e:
        if e.status_code == 409:
            logger.warning("Cargo is already deployed and running")
        else:
            raise e
    return True
