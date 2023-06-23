import logging
from tabulate import tabulate
from typing import List

from gefyra.configuration import ClientConfiguration

from .utils import stopwatch


logger = logging.getLogger(__name__)


def get_containers_and_print(connection_name=""):
    from gefyra.api import list_containers

    containers = list_containers(connection_name=connection_name)
    print(
        tabulate(
            containers, headers=["NAME", "IP ADDRESS", "NAMESPACE"], tablefmt="plain"
        )
    )


def get_bridges_and_print(connection_name=""):
    from gefyra.api import list_gefyra_bridges

    gefyra_bridges = list_gefyra_bridges(connection_name=connection_name)
    if gefyra_bridges:
        for gefyra_bridge in gefyra_bridges:
            print(gefyra_bridge)
    else:
        logger.info("No active bridges found")


@stopwatch
def list_gefyra_bridges(connection_name="") -> List[str]:
    from gefyra.local.bridge import get_all_gefyrabridges

    config = ClientConfiguration(connection_name=connection_name)

    # Check if kubeconfig is available through running Cargo
    ireqs = []
    for ireq in get_all_gefyrabridges(config):
        ireqs.append(ireq["metadata"]["name"])
    return ireqs


@stopwatch
def list_containers(connection_name="") -> List[str]:
    from gefyra.local.bridge import get_all_containers

    config = ClientConfiguration(connection_name=connection_name)

    return get_all_containers(config)
