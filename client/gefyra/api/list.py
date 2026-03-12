import logging
from gefyra.exceptions import ClientConfigurationError
from gefyra.types import GefyraLocalContainer
from typing import List, Optional, Tuple

from gefyra.configuration import ClientConfiguration

from .utils import stopwatch


logger = logging.getLogger(__name__)


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
