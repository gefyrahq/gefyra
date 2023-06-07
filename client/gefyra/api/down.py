import logging

from gefyra.configuration import ClientConfiguration

from .utils import stopwatch


logger = logging.getLogger(__name__)


@stopwatch
def down() -> bool:
    from gefyra.cluster.manager import uninstall_operator
    from gefyra.local.cargo import remove_cargo_container
    from gefyra.local.networking import (
        handle_remove_network,
        kill_remainder_container_in_network,
    )
    from gefyra.local.bridge import remove_interceptrequest_remainder

    config = ClientConfiguration()
    try:
        logger.info("Removing running bridges")
        remove_interceptrequest_remainder(config)
        logger.info("Uninstalling Operator")
        uninstall_operator(config)
        logger.info("Removing Cargo")
    except Exception as e:
        logger.error(f"Could not remove all Gefyra cluster components: {e}")

    remove_cargo_container(config)
    kill_remainder_container_in_network(config, config.NETWORK_NAME)
    handle_remove_network(config)
    return True
