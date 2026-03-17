import json
import logging
import os
import socket
import time
from dataclasses import dataclass, fields
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

import docker

from gefyra.configuration import get_gefyra_config_location
from gefyra.exceptions import CommandTimeoutError, GefyraConnectionError
from gefyra.local.clients import handle_get_gefyraclient
from gefyra.local.minikube import detect_minikube_config
from gefyra.local.networking import get_or_create_gefyra_network
from gefyra.local.utils import WatchEventsMixin, handle_docker_get_or_create_container
from gefyra.types.stowaway import StowawayConfig, StowawayParameter

if TYPE_CHECKING:
    from docker.models.networks import Network

    from gefyra.configuration import ClientConfiguration


logger = logging.getLogger(__name__)


LOCAL_SERVER = "#local#"


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
    wireguard_mtu: Optional[str] = None

    def __getattribute__(self, name):
        if name == "gefyra_server":
            from gefyra.configuration import ClientConfiguration

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
    _wg_handshake: str | None = None
    _created: Optional[str] = None
    provider_parameter: Optional[StowawayParameter] = None
    provider_config: Optional[StowawayConfig] = None
    service_account_name: Optional[str] = None
    service_account: Optional[Dict[str, str]] = None

    def __init__(self, gclient: dict[str, Any], config: "ClientConfiguration"):
        self._init_data(gclient)
        self._config = config

    def inspect(self, fetch_events: bool = False) -> dict[str, str | List[str]]:
        res = {
            "client_id": self.client_id,
            "uid": self.uid,
            "state": GefyraClientState(self._state).value,
            "state_transitions": self.state_transitions,
            "wg_status": self.wg_status,
            "created": self.state_transitions.get("CREATING", "Creating..."),
            "wg_handshake": self._wg_handshake or "-",
        }

        if fetch_events:
            events: List[str] = []
            self.watch_events(events.append, None, 1)
            res["events"] = events
        return res

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
            except Exception:
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

    def wait_for_state(self, desired_state: GefyraClientState, timeout: int = 60):
        start_time = time.time()
        while True:
            if self.state == desired_state:
                return
            if time.time() - start_time > timeout:
                raise CommandTimeoutError(
                    f"Timeout waiting for client {self.client_id} to reach state {desired_state}"
                )
            time.sleep(2)

    @property
    def state(self) -> GefyraClientState:
        self.update()
        return GefyraClientState(self._state)

    @property
    def state_transitions(self):
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
        wireguard_mtu: Optional[int] = None,
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

    def disconnect(
        self,
        nowait: bool = False,
        update_callback: Callable[[str], None] | None = None,
        timeout: int = 60,
    ) -> bool:
        get_or_create_gefyra_network(self._config)
        if update_callback:
            update_callback(
                f"Stopping Cargo container for client '{self.client_id}'..."
            )
        try:
            cargo_container = self._config.DOCKER.containers.get(
                f"{self._config.CARGO_CONTAINER_NAME}",
            )
            cargo_container.stop()
        except docker.errors.NotFound:
            pass
        if update_callback:
            update_callback(f"Deactivating connection for client '{self.client_id}'...")
        self.deactivate_connection()
        if not nowait:
            if update_callback:
                update_callback(
                    f"Waiting for client '{self.client_id}' to be in state 'WAITING'..."
                )
            self.wait_for_state(GefyraClientState.WAITING, timeout)
        return True

    def connect(
        self,
        update_callback: Callable[[str], None] | None = None,
        cargo_container=None,
        minikube_profile=None,
        timeout: int | None = None,
    ):
        import kubernetes

        from gefyra.local.cargo import create_wireguard_config, get_cargo_ip_from_netaddress, probe_wireguard_connection

        _retry = 0

        while _retry < 10:
            gefyra_network = get_or_create_gefyra_network(self._config)
            try:
                if update_callback:
                    update_callback(
                        "Activating connection with appointed local "
                        f"Gefyra network {gefyra_network.attrs['IPAM']['Config'][0]['Subnet']} ..."
                    )
                self.activate_connection(
                    gefyra_network.attrs["IPAM"]["Config"][0]["Subnet"]
                )
                break
            except kubernetes.client.exceptions.ApiException as e:
                _retry += 1
                if e.status == 500:
                    logger.debug(
                        f"Could not activate connection, retrying {_retry}/10..."
                    )
                    # if the given subnet is taken in the cluster (by another client), recreate the network and try again
                    # hopefully the IPAM config will give a new subnet
                    gefyra_network.remove()
        else:
            raise GefyraConnectionError("Could not activate connection") from None

        # busy wait for the client to enter the ACTIVE state
        _i = 0
        timeout = timeout or self._config.CONNECTION_TIMEOUT
        while _i < timeout:
            if self.state == GefyraClientState.ACTIVE:
                if update_callback:
                    update_callback("Cluster connection activated")
                break
            else:
                _i += 1
                time.sleep(1)
        else:
            raise GefyraConnectionError("Could not activate connection") from None
        self.update()

        # since this connection was (re)activated, save the current wireguard config (again)
        wg_conf = os.path.join(
            get_gefyra_config_location(), f"{self._config.CONNECTION_NAME}.conf"
        )
        if not self.provider_config:
            raise GefyraConnectionError(
                "Could not get provider config for client"
            ) from None

        if self._config.CARGO_ENDPOINT is None:
            self._config.CARGO_ENDPOINT = self.provider_config.pendpoint
        logger.debug(self._config.CARGO_ENDPOINT)
        # busy wait to resolve the cargo endpoint, making sure it's actually resolvable from this host
        _i = 0
        while _i < self._config.CONNECTION_TIMEOUT:
            try:
                socket.gethostbyname_ex(self._config.CARGO_ENDPOINT.split(":")[0])
                break
            except (
                socket.gaierror,
                socket.herror,
            ):  # [Errno -2] Name or service not known
                logger.debug(
                    f"Could not resolve host '{self._config.CARGO_ENDPOINT.split(':')[0]}', "
                    f"retrying {_i}/{self._config.CONNECTION_TIMEOUT}..."
                )
                _i += 1
                time.sleep(1)
        else:
            raise GefyraConnectionError(
                f"Cannot resolve host '{self._config.CARGO_ENDPOINT.split(':')[0]}'."
            ) from None

        with open(wg_conf, "w") as f:
            f.write(
                create_wireguard_config(
                    self.provider_config,
                    self._config.CARGO_ENDPOINT,
                    self._config.WIREGUARD_MTU,
                )
            )

        cargo_ip_address = get_cargo_ip_from_netaddress(
            gefyra_network.attrs["IPAM"]["Config"][0]["Subnet"]
        )

        try:
            if not cargo_container:
                if update_callback:
                    update_callback(
                        "Pulling and starting local Cargo container (client-side Wireguard endpoint)"
                    )
                cargo_container = handle_docker_get_or_create_container(
                    self._config,
                    f"{self._config.CARGO_CONTAINER_NAME}",
                    self._config.CARGO_IMAGE,
                    detach=True,
                    cap_add=["NET_ADMIN"],
                    privileged=True,
                    volumes=[
                        "/var/run/docker.sock:/var/run/docker.sock",
                        f"{wg_conf}:/config/wg0.conf",
                    ],
                    pid_mode="host",
                )

                if minikube_profile:
                    mini_conf = detect_minikube_config(minikube_profile)
                    if mini_conf["network_name"]:
                        logger.debug("Joining minikube network")
                        minikube_net: "Network" = self._config.DOCKER.networks.get(
                            mini_conf["network_name"]
                        )
                        minikube_net.connect(cargo_container)
                logger.debug(f"Cargo gefyra net ip address: {cargo_ip_address}")
                gefyra_network.connect(cargo_container, ipv4_address=cargo_ip_address)
            cargo_container.start()
            time.sleep(1)
        except docker.errors.APIError as e:
            try:
                cargo_container and cargo_container.remove()
            except docker.errors.APIError:
                pass
            raise GefyraConnectionError(
                f"Could not start Cargo container: {e}"
            ) from None

        # Confirm the wireguard connection working
        logger.debug("Checking wireguard connection")
        if update_callback:
            update_callback("Checking Wireguard connectivity...")
        probe_wireguard_connection(self._config)
        return True
