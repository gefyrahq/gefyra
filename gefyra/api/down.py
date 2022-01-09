import logging

from gefyra.cluster.manager import uninstall_operator
from gefyra.configuration import default_configuration
from gefyra.local.cargo import remove_cargo_container
from gefyra.local.networking import handle_remove_network

from .utils import stopwatch

logger = logging.getLogger(__name__)


@stopwatch
def down(config=default_configuration) -> bool:
    logger.info("Uninstalling Operator")
    uninstall_operator(config)
    logger.info("Removing Cargo")
    remove_cargo_container(config)
    logger.info("Removing Docker network")
    handle_remove_network(config)
    return True
