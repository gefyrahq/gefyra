from dataclasses import dataclass
from enum import Enum
import json
import logging

from gefyra.types.bridge_mount import GefyraBridgeMount
from gefyra.types.bridge import GefyraBridge, ExactMatchHeader
from gefyra.types.client import (
    GefyraClient,
    GefyraClientConfig,
    GefyraClientState,
    LOCAL_SERVER,
)
from gefyra.types.install import GefyraInstallOptions
from gefyra.types.stowaway import StowawayParameter, StowawayConfig


__all__ = [
    "GefyraInstallOptions",
    "GefyraClient",
    "GefyraBridgeMount",
    "GefyraBridge",
    "ExactMatchHeader",
    "StowawayParameter",
    "StowawayConfig",
    "GefyraClientConfig",
    "GefyraClientState",
    "LOCAL_SERVER",
]


logger = logging.getLogger(__name__)


@dataclass
class GefyraConnectionItem:
    name: str
    version: str
    created: str
    status: str
    client_status: str
    wireguard_probe: bool = False

    @property
    def json(self):
        return json.dumps(self.__dict__)


@dataclass
class GefyraClusterStatus:
    # is a kubernetes cluster reachable
    connected: bool
    # is the operator running
    operator: bool
    operator_image: str
    # is stowaway running
    stowaway: bool
    stowaway_image: str
    # the gefyra namespace is available
    namespace: bool
    # operator webhook
    operator_webhook: bool


@dataclass
class GefyraClientStatus:
    version: str
    # is cargo running
    cargo: bool
    cargo_image: str
    # is gefyra network available
    network: bool
    # is gefyra client connected with gefyra cluster
    connection: bool
    # amount of containers running in gefyra
    containers: int
    # amount of active bridges
    bridges: int
    # current kubeconfig file
    kubeconfig: str
    # current kubeconfig context
    context: str
    # wireguard endpoint
    cargo_endpoint: str


class StatusSummary(str, Enum):
    UP = "Gefyra is up and connected"
    DOWN = "Gefyra is not running"
    INCOMPLETE = "Gefyra is not running properly"


@dataclass
class GefyraStatus:
    summary: StatusSummary
    cluster: GefyraClusterStatus
    client: GefyraClientStatus


@dataclass
class GefyraLocalContainer:
    """
    A container managed(/started) by Gefyra
    """

    id: str
    short_id: str
    name: str
    address: str
    namespace: str
