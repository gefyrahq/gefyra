from dataclasses import dataclass, field, fields
from enum import Enum
import json
import logging
from typing import Any, Dict, Optional

from gefyra.configuration import ClientConfiguration, __VERSION__
from gefyra.local.clients import handle_get_gefyraclient

logger = logging.getLogger(__name__)


@dataclass
class StowawayParameter:
    # the subnet for a client
    subnet: str


@dataclass
class GefyraClientConfig:
    client_id: str
    kubernetes_server: str
    provider: str
    token: str
    namespace: str
    ca_crt: str
    gefyra_server: str

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


@dataclass
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
    service_account: Optional[Dict[str, str]] = None

    def __init__(
        self,
        gclient: dict[str, Any],
    ):
        config = ClientConfiguration()
        self._init_data(gclient)
        self._config = config

    def _init_data(self, _object: dict[str, Any]):
        self.client_id = _object["metadata"]["name"]
        self.uid = _object["metadata"]["uid"]
        self.provider = _object.get("provider", "")
        self._state = _object.get("state", "")
        self._state_transitions = _object.get("stateTransitions", {})
        self.service_account_name = _object.get("serviceAccountName")
        self.service_account = _object.get("serviceAccountData", {})
        if (
            providerparams := _object.get("providerParameter")
        ) and self.provider == "stowaway":
            self.provider_parameter = StowawayParameter(
                subnet=providerparams.get("subnet")
            )
        if (
            providerconfig := _object.get("providerConfig")
        ) and self.provider == "stowaway":
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
                        "iport": str(_v.iport),
                        "iprivatekey": _v.iprivatekey,
                        "pallowedips": _v.pallowedips,
                        "pendpoint": _v.pendpoint,
                        "ppublickey": _v.ppublickey,
                    }
                else:
                    data[_field.name] = _v
        return data

    @property
    def state(self) -> GefyraClientState:
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

    def get_client_config(
        self, gefyra_server: str, k8s_server: str
    ) -> GefyraClientConfig:
        if not bool(self.service_account):
            self.update()
        if self.service_account:
            return GefyraClientConfig(
                client_id=self.client_id,
                kubernetes_server=k8s_server or self._config.get_kubernetes_api_url(),
                provider=self.provider,
                token=self.service_account["token"],
                namespace=self.service_account["namespace"],
                ca_crt=self.service_account["ca.crt"],
                gefyra_server=gefyra_server,
            )
        else:
            raise RuntimeError("Cannot get client config, no service account found.")

    def activate_connection(self, subnet: str):
        _state = self.state
        if _state == GefyraClientState.ACTIVE:
            return
        elif _state == GefyraClientState.WAITING:
            logger.debug(f"Activating connection for client {self.client_id}")
            self._config.K8S_CUSTOM_OBJECT_API.patch_namespaced_custom_object(
                group="gefyra.dev",
                version="v1",
                namespace=self._config.NAMESPACE,
                plural="gefyraclients",
                name=self.client_id,
                body={"providerParameter": {"subnet": subnet}},
            )
        else:
            raise RuntimeError(
                f"Cannot activate connection for client {self.client_id}, state is"
                f" {self.state}"
            )

    def deactivate_connection(self):
        _state = self.state
        if _state == GefyraClientState.WAITING:
            return
        elif _state == GefyraClientState.ACTIVE:
            logger.debug(f"Deactivating connection for client {self.client_id}")
            self._config.K8S_CUSTOM_OBJECT_API.patch_namespaced_custom_object(
                group="gefyra.dev",
                version="v1",
                namespace=self._config.NAMESPACE,
                plural="gefyraclients",
                name=self.client_id,
                body={"providerParameter": None},
            )
        else:
            raise RuntimeError(
                f"Cannot deactivate connection for client {self.client_id}, state is"
                f" {self.state}"
            )


@dataclass
class GefyraInstallOptions:
    namespace: str = field(
        default_factory=lambda: "gefyra",
        metadata=dict(
            help="The namespace to install Gefyra into (default: gefyra)", short="ns"
        ),
    )
    version: str = field(
        default_factory=lambda: __VERSION__,
        metadata=dict(
            help=(
                "Set the Operator version; components are created according to this"
                f" Gefyra version (default: {__VERSION__})"
            )
        ),
    )
    service_type: str = field(
        default_factory=lambda: "NodePort",
        metadata=dict(
            help=(
                "The Kubernetes service for Stowaway to expose the Wireguard endpoint"
                " (default: NodePort)"
            )
        ),
    )
    service_port: int = field(
        default_factory=lambda: 31820,
        metadata=dict(
            help=(
                "The port for Stowaway to expose the Wireguard endpoint (default:"
                " 31820)"
            )
        ),
    )
    service_labels: Dict[str, str] = field(
        default_factory=lambda: {},
        metadata=dict(
            help="Additional Kubernetes labels for the Stowaway service (default: [])",
            type="array",
        ),
    )
    service_annotations: Dict[str, str] = field(
        default_factory=lambda: {},
        metadata=dict(
            help="Kubernetes annotations for the Stowaway service (default: [])",
            type="array",
        ),
    )
