from dataclasses import dataclass
from enum import Enum
import json
import logging
from typing import Optional

from gefyra.configuration import ClientConfiguration, __VERSION__


__all__ = [
    "GefyraInstallOptions",
    "GefyraClient",
    "GefyraBridgeMount",
    "GefyraBridge",
    "ExactMatchHeader",
]


logger = logging.getLogger(__name__)


LOCAL_SERVER = "#local#"


@dataclass
class StowawayParameter:
    # the subnet for a client
    subnet: str


@dataclass
class GefyraClientConfig:
    client_id: str
    kubernetes_server: str
    provider: str
    namespace: str
    gefyra_server: str
    token: str | None = None
    ca_crt: str | None = None
    registry: Optional[str] = None
    wireguard_mtu: Optional[str] = "1340"

    def __getattribute__(self, name):
        if name == "gefyra_server":
            if super().__getattribute__(name) == LOCAL_SERVER:
                return ClientConfiguration().CARGO_ENDPOINT
        return super().__getattribute__(name)

    @property
    def json(self):
        return json.dumps(self.__dict__)

    @classmethod
    def from_json_str(cls, json_data: str):
        data = json.loads(json_data)
        return cls(**data)


@dataclass
class StowawayConfig:
    # the wireguard connection data
    # Interface.Address: 192.168.99.2
    iaddress: str
    # Interface.DNS: 192.168.99.1
    idns: str
    # Interface.ListenPort: 51820
    iport: int
    # Interface.PrivateKey: MFQ3v+...=
    iprivatekey: str
    # Peer.AllowedIPs: 0.0.0.0/0, ::/0
    pallowedips: str
    # Peer.Endpoint: 95.91.248.4:31820
    pendpoint: str
    # Peer.PublicKey: sy8jXi7...=
    ppublickey: str
    # Peer.PresharedKey: WCWY20...=
    presharedkey: str


class GefyraClientState(Enum):
    REQUESTED = "REQUESTED"
    CREATING = "CREATING"
    WAITING = "WAITING"
    ENABLING = "ENABLING"
    ACTIVE = "ACTIVE"
    DISABLING = "DISABLING"
    TERMINATING = "TERMINATING"
    ERROR = "ERROR"


@dataclass
class GefyraConnectionItem:
    name: str
    version: str
    created: str
    status: str


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


from .bridge_mount import GefyraBridgeMount
from .bridge import GefyraBridge, ExactMatchHeader
from .client import GefyraClient
from .install import GefyraInstallOptions
