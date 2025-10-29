from dataclasses import dataclass, fields
import logging
from typing import Any, Dict, Optional

from gefyra.configuration import ClientConfiguration
from gefyra.local.clients import handle_get_gefyraclient
from gefyra.types import (
    GefyraClientConfig,
    GefyraClientState,
    StowawayConfig,
    StowawayParameter,
)
from gefyra.local.utils import WatchEventsMixin

logger = logging.getLogger(__name__)


@dataclass
class GefyraClient(WatchEventsMixin):
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
    _wg_status: Optional[Dict[str, str]] = None
    _wg_handshake: Optional[Dict[str, str]] = None
    _created: Optional[str] = None
    provider_parameter: Optional[StowawayParameter] = None
    provider_config: Optional[StowawayConfig] = None
    service_account_name: Optional[str] = None
    service_account: Optional[Dict[str, str]] = None

    def __init__(self, gclient: dict[str, Any], config: ClientConfiguration):
        self._init_data(gclient)
        self._config = config

    def _init_data(self, _object: dict[str, Any]):
        self.client_id = _object["metadata"]["name"]
        self.name = _object["metadata"]["name"]
        self.uid = _object["metadata"]["uid"]
        self.namespace = _object["metadata"]["namespace"]
        self.provider = _object.get("provider", "")
        self._state = _object.get("state", "")
        if _object.get("status", None) and "wireguard" in _object["status"]:
            try:
                self.wg_status = _object["status"]["wireguard"]
                if "latest_handshake" in self.wg_status:
                    self._wg_handshake = self.wg_status["latest_handshake"]
                else:
                    self._wg_handshake = "No handshake"
            except Exception as p:
                pass
        else:
            self.wg_status = None
        self._created = _object["metadata"].get("creationTimestamp", "")
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
                presharedkey=providerconfig.get("Peer.PresharedKey"),
            )

    def as_dict(self) -> dict[str, Any]:
        data = {}
        for _field in fields(self):
            if _v := getattr(self, _field.name):
                if type(_v) is StowawayParameter:
                    data["providerParameter"] = {"subnet": _v.subnet}
                elif type(_v) is StowawayConfig:
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
        self,
        gefyra_server: str,
        k8s_server: str = "",
        registry: Optional[str] = None,
        wireguard_mtu: Optional[int] = 1340,
    ) -> GefyraClientConfig:
        if not bool(self.service_account):
            self.update()
        return GefyraClientConfig(
            client_id=self.client_id,
            kubernetes_server=k8s_server or self._config.get_kubernetes_api_url(),
            provider=self.provider,
            token=self.service_account.get("token"),
            namespace=self.namespace,
            ca_crt=self.service_account.get("ca.crt"),
            gefyra_server=gefyra_server,
            registry=registry,
            # if somehow the mtu is not given make sure to have null as json value
            wireguard_mtu=str(wireguard_mtu) if wireguard_mtu else None,
        )

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
