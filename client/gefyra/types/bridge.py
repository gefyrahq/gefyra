from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from gefyra.configuration import ClientConfiguration
from gefyra.local.utils import WatchEventsMixin


@dataclass
class CarrierHeaderMatchBase:
    # the name of the header to match
    name: str
    # the exact header value to match
    value: str


@dataclass
class CarrierPathMatchBase:
    # the path to match
    path: str


@dataclass
class ExactMatchHeader(CarrierHeaderMatchBase):
    type: str = "exact"


@dataclass
class PrefixMatchHeader(CarrierHeaderMatchBase):
    type: str = "prefix"


@dataclass
class RegexMatchHeader(CarrierHeaderMatchBase):
    type: str = "regex"


@dataclass
class ExactMatchPath(CarrierPathMatchBase):
    type: str = "exact"


@dataclass
class PrefixMatchPath(CarrierPathMatchBase):
    type: str = "prefix"


@dataclass
class RegexMatchPath(CarrierPathMatchBase):
    type: str = "regex"


@dataclass
class GefyraBridge(WatchEventsMixin):
    """
    A GefyraBridge object
    """

    # the name of the bridge
    name: str
    # the client_id of the user requesting the bridge
    client: str
    # the ip if the local container
    local_container_ip: str
    # mapping ports [local:remote]
    port_mappings: List[str]
    # the name of the GefyraBridgeMount object
    target: str
    # also handle probes of this container (legacy)
    handle_probes: bool = True

    # the state of the bridge
    _state: str | None = None
    _state_transitions: Dict[str, str] | None = None
    _created: Optional[str] | None = None

    # bridge provider {carrier, carrier2}
    provider: str = "carrier2"
    # the connection provider, needed to create a reverse path beweet cluster and local {stowaway}
    connection_provider: str = "stowaway"
    # additional provider parameters for this bridge
    exact_match_headers: List[ExactMatchHeader] | None = None

    # legacy (global bridge)
    target_namespace: str = ""
    target_container: str = ""

    @classmethod
    def from_raw(
        cls, bridge_raw: Dict[Any, Any], config: ClientConfiguration
    ) -> "GefyraBridge":
        bridge = cls(
            provider=bridge_raw["provider"],
            name=bridge_raw["metadata"]["name"],
            client=bridge_raw["client"],
            local_container_ip=bridge_raw["destinationIP"],
            port_mappings=bridge_raw["portMappings"] or [],
            target_container=bridge_raw["targetContainer"],
            target_namespace=bridge_raw["targetNamespace"],
            target=bridge_raw["target"],
            exact_match_headers=bridge_raw.get("providerParameter"),
        )
        bridge._state = bridge_raw["state"]
        bridge._state_transitions = bridge_raw.get("stateTransitions", None)
        bridge._created = bridge_raw["metadata"].get("creationTimestamp", None)
        bridge._config = config
        return bridge

    def get_k8s_bridge_body(self, config: ClientConfiguration):
        from gefyra.local.bridge import get_bridge_rules

        if self.exact_match_headers:
            params = {"rules": get_bridge_rules(self.exact_match_headers)}
        else:
            params = {}
        return {
            "apiVersion": "gefyra.dev/v1",
            "kind": "gefyrabridge",
            "metadata": {
                "name": self.name,
                "namespace": config.NAMESPACE,
                "labels": {
                    "gefyra.dev/bridge-mount": self.target,
                    "gefyra.dev/client": self.client,
                },
            },
            "provider": self.provider,
            "connectionProvider": self.connection_provider,
            "providerParameter": params,
            "client": self.client,
            "destinationIP": self.local_container_ip,
            "target": self.target,
            "targetNamespace": self.target_namespace,
            "targetContainer": self.target_container,
            "portMappings": self.port_mappings,
            "handleProbes": self.handle_probes,
        }
