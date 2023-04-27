from dataclasses import dataclass
from enum import Enum
import logging
from typing import Any, Dict, Optional

from attr import fields
from gefyra.configuration import ClientConfiguration, default_configuration
from gefyra.local.clients import handle_get_gefyraclient

logger = logging.getLogger(__name__)

@dataclass
class StowawayParameter:
    # the subnet for a client
    subnet: str

@dataclass
class GefyraClientConfig:
    kubernetes_server: str
    provider: str
    token: str
    namespace: str
    ca_crt: str
    gefyra_server: str

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
    # Peer.PublicKey: sy8jXi7S7rUGpqLnqgKnmHFXylqQdvCPCfhBAgSVGEM=
    ppublickey: str


class GefyraClientState(Enum):
    REQUESTED = "REQUESTED"
    CREATING = "CREATING"
    WAITING = "WAITING"
    ENABLING = "ENABLING"
    ACTIVE = "ACTIVE"
    DISABLING = "DISABLING"
    TERMINATING = "TERMINATING"
    ERROR = "ERROR"


class GefyraClient:
    # the id of the client
    client_id: str
    # the namespace this cluster runs in the host cluster
    namespace: str
    # the uid from Kubernetes for this object
    uid: str
    # the labels of this Gefyra object
    labels: Dict[str, str]
    # the provider of the client, always 'stowaway' in this version of Gefyra
    provider: str

    # the state of the client
    _state: str
    _state_transitions: Dict[str, str]
    provider_parameter: Optional[StowawayParameter] = None
    provider_config: Optional[StowawayConfig] = None
    service_account_name: Optional[str] = None
    service_account: Dict[str, str]

    def __init__(
        self, gclient: dict[str, Any], config: ClientConfiguration = default_configuration
    ):
        self._init_data(gclient)
        self._config = config


    def _init_data(self, _object: dict[str, Any]):
        self.client_id = _object["metadata"]["name"]
        self.provider = _object.get("provider")
        self._state = _object.get("state")
        self._state_transitions = _object.get("stateTransitions", {})
        self.service_account_name = _object.get("serviceAccountName")
        self.service_account = _object.get("serviceAccountData", {})
        if (
            providerparams := _object.get("providerParameter")
            and self.provider == "stowaway"
        ):
            self.provider_parameter = StowawayParameter(
                subnet=providerparams.get("subnet")
            )
        if (
            providerconfig := _object.get("providerConfig")
            and self.provider == "stowaway"
        ):
            self.provider_config = StowawayConfig(
                iaddress=providerconfig.get("Interface.Address"),
                idns=providerconfig.get("Interface.DNS"),
                iport=providerconfig.get("Interface.ListenPort"),
                iprivatekey=providerconfig.get("Interface.PrivateKey"),
                pallowedips=providerconfig.get("Peer.AllowedIPs"),
                pendpoint=providerconfig.get("Peer.Endpoint"),
                ppublickey=providerconfig.get("Peer.PublicKey"),
            )

    def as_dict(self) -> dict[str, Any]:
        data = {}
        for _field in fields(self):
            if _v := getattr(self, _field.name):
                if type(_v) == StowawayParameter:
                    data["providerParameter"] = {"subnet": _v.subnet}
                elif type(_v) == StowawayConfig:
                    data["providerConfig"] = {
                        "iaddress": _v.iaddress,
                        "idns": _v.idns,
                        "iport": _v.iport,
                        "iprivatekey": _v.iprivatekey,
                        "pallowedips": _v.pallowedips,
                        "pendpoint": _v.pendpoint,
                        "ppublickey": _v.ppublickey,
                    }
                else:
                    data[_field.name] = _v
        return data
    
    @property
    def state(self):
        self.update()
        return GefyraClientState(self._state)
    
    @property
    def state_transitions(self):
        self.update()
        return self._state_transitions

    def update(self):
        logger.debug(f"Fetching object GefyraClient {self.client_id}")
        gclient = handle_get_gefyraclient(self._config, self.client_id)
        self._init_data(gclient)

    def get_client_config(self, gefyra_server: str, k8s_server: str = None) -> GefyraClientConfig:
        if not bool(self.service_account):
            self.update()
        if bool(self.service_account):
            return GefyraClientConfig(
                kubernetes_server=k8s_server or self._config.get_kubernetes_api_url(),
                provider=self.provider,
                token=self.service_account["token"],
                namespace=self.service_account["namespace"],
                ca_crt=self.service_account["ca.crt"],
                gefyra_server=gefyra_server,
            )
        else:
            raise RuntimeError("Cannot get client config, no service account found.")

