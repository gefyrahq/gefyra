import logging
from tabulate import tabulate
from typing import List

from gefyra.configuration import default_configuration

from .utils import stopwatch


logger = logging.getLogger(__name__)


def get_containers_and_print(config: default_configuration):
    from gefyra.api import list_containers

    containers = list_containers(config=config)
    print(
        tabulate(
            containers, headers=["NAME", "IP ADDRESS", "NAMESPACE"], tablefmt="plain"
        )
    )


def get_bridges_and_print(config: default_configuration):
    from gefyra.api import list_interceptrequests

    ireqs = list_interceptrequests(config=config)
    if ireqs:
        for ireq in ireqs:
            print(ireq)
    else:
        logger.info("No active bridges found")


@stopwatch
def list_interceptrequests(config=default_configuration) -> List[str]:
    from gefyra.local.bridge import get_all_interceptrequests
    from gefyra.local.utils import (
        set_gefyra_network_from_cargo,
        set_kubeconfig_from_cargo,
    )

    # Check if kubeconfig is available through running Cargo
    config = set_kubeconfig_from_cargo(config)

    config = set_gefyra_network_from_cargo(config)
    ireqs = []
    for ireq in get_all_interceptrequests(config):
        ireqs.append(ireq["metadata"]["name"])
    return ireqs


@stopwatch
def list_containers(config=default_configuration) -> List[str]:
    from gefyra.local.bridge import get_all_containers
    from gefyra.local.utils import set_gefyra_network_from_cargo

    config = set_gefyra_network_from_cargo(config)

    return get_all_containers(config)
