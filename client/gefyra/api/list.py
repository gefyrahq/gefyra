import logging
from tabulate import tabulate
from typing import List

from gefyra.configuration import ClientConfiguration

from .utils import stopwatch


logger = logging.getLogger(__name__)


def get_containers_and_print():
    from gefyra.api import list_containers

    config = ClientConfiguration()

    containers = list_containers(config=config)
    print(
        tabulate(
            containers, headers=["NAME", "IP ADDRESS", "NAMESPACE"], tablefmt="plain"
        )
    )


def get_bridges_and_print():
    from gefyra.api import list_interceptrequests

    config = ClientConfiguration()

    ireqs = list_interceptrequests(config=config)
    if ireqs:
        for ireq in ireqs:
            print(ireq)
    else:
        logger.info("No active bridges found")


@stopwatch
def list_interceptrequests() -> List[str]:
    from gefyra.local.bridge import get_all_gefyrabridges

    config = ClientConfiguration()

    # Check if kubeconfig is available through running Cargo
    ireqs = []
    for ireq in get_all_gefyrabridges(config):
        ireqs.append(ireq["metadata"]["name"])
    return ireqs


@stopwatch
def list_containers() -> List[str]:
    from gefyra.local.bridge import get_all_containers

    config = ClientConfiguration()

    return get_all_containers(config)
