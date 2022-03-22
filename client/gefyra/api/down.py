import logging

from gefyra.configuration import default_configuration

from .utils import stopwatch

logger = logging.getLogger(__name__)


@stopwatch
def down(config=default_configuration) -> bool:
    from gefyra.cluster.manager import uninstall_operator
    from gefyra.local.cargo import remove_cargo_container
    from gefyra.local.networking import (
        handle_remove_network,
        kill_remainder_container_in_network,
    )
    from gefyra.local.bridge import remove_interceptrequest_remainder

    logger.info("Removing running bridges")
    remove_interceptrequest_remainder(config)
    logger.info("Uninstalling Operator")
    uninstall_operator(config)
    logger.info("Removing Cargo")
    remove_cargo_container(config)
    logger.info("Stopping remainder container from Gefyra network")
    kill_remainder_container_in_network(config, config.NETWORK_NAME)
    logger.info("Removing Docker network")
    handle_remove_network(config)
    return True
