import logging
from gefyra.exceptions import ClientConfigurationError
from gefyra.types import GefyraBridge, GefyraLocalContainer
from tabulate import tabulate
from typing import List, Optional, Tuple

from gefyra.configuration import ClientConfiguration

from .utils import stopwatch, wrap_bridge


logger = logging.getLogger(__name__)


def get_containers_and_print(connection_name: Optional[str] = None):
    from gefyra.api import list_containers

    containers = list_containers(connection_name=connection_name)
    print(
        tabulate(
            containers, headers=["NAME", "IP ADDRESS", "NAMESPACE"], tablefmt="plain"
        )
    )


def get_bridges_and_print(connection_name: Optional[str] = None):
    from gefyra.api import list_gefyra_bridges

    gefyra_bridges = list_gefyra_bridges(connection_name=connection_name)
    if gefyra_bridges:
        for gefyra_bridge in gefyra_bridges:
            print(gefyra_bridge)
    else:
        logger.info("No active bridges found")


@stopwatch
def list_gefyra_bridges(
    connection_name: Optional[str] = None,
) -> List[Tuple[str, List[GefyraBridge]]]:
    from gefyra.local.bridge import get_all_gefyrabridges
    from gefyra import api

    conns = api.list_connections()
    if connection_name:
        if connection_name not in [conns.name for conns in conns]:
            raise ClientConfigurationError(
                f"Connection {connection_name} does not exist. Please create it first."
            )
        obridges = get_all_gefyrabridges(
            ClientConfiguration(connection_name=connection_name)
        )
        return [(connection_name, list(map(wrap_bridge, obridges)))]
    else:
        bridges = []
        for conn in conns:
            bridges.append(
                (
                    conn.name,
                    list(
                        map(
                            wrap_bridge,
                            get_all_gefyrabridges(
                                ClientConfiguration(connection_name=conn.name)
                            ),
                        )
                    ),
                )
            )
        return bridges


@stopwatch
def list_containers(
    connection_name: Optional[str] = None,
) -> List[Tuple[str, List[GefyraLocalContainer]]]:
    from gefyra.local.bridge import get_all_containers
    from gefyra import api

    conns = api.list_connections()
    if connection_name:
        if connection_name not in [conns.name for conns in conns]:
            raise ClientConfigurationError(
                f"Connection {connection_name} does not exist. Please create it first."
            )
        return [
            (
                connection_name,
                get_all_containers(
                    ClientConfiguration(connection_name=connection_name)
                ),
            )
        ]
    else:
        return [
            (
                conn.name,
                get_all_containers(ClientConfiguration(connection_name=conn.name)),
            )
            for conn in conns
        ]
