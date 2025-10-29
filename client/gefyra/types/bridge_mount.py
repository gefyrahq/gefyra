from dataclasses import dataclass
import logging
from typing import Any, Dict, Optional

from gefyra.configuration import ClientConfiguration
from gefyra.local.mount import get_gefyrabridgemount
from gefyra.types import StowawayParameter
from gefyra.local.utils import WatchEventsMixin

logger = logging.getLogger(__name__)


@dataclass
class GefyraBridgeMount(WatchEventsMixin):
    # the id of the mount
    mount_id: str
    # the namespace this cluster runs in the host cluster
    namespace: str
    # the uid from Kubernetes for this object
    uid: str
    # the labels of this Gefyra object
    labels: Dict[str, str]
    # the provider of the mount
    provider: str
    # target
    target: str
    target_container: str
    target_namespace: str

    # the state of the mount
    _state: str
    _state_transitions: Dict[str, str]
    _created: Optional[str]
    provider_parameter: Optional[StowawayParameter] = None

    @classmethod
    def from_raw(cls, config: ClientConfiguration, gbridgemount: dict[str, Any]):
        return cls(config, gbridgemount)

    def __init__(self, config: ClientConfiguration, gbridgemount: dict[str, Any]):
        self._init_data(gbridgemount)
        self._config = config

    def _init_data(self, _object: dict[str, Any]):
        self.mount_id = _object["metadata"]["name"]
        self.name = _object["metadata"]["name"]
        self.uid = _object["metadata"]["uid"]
        self.provider = _object.get("provider", "")
        self._state = _object.get("state", "")
        self._state_transitions = _object.get("stateTransitions", {})
        self._created = _object["metadata"].get("creationTimestamp", None)
        self.target = _object.get("target", "")
        self.target_container = _object.get("targetContainer", "")
        self.target_namespace = _object.get("targetNamespace", "")
        self.namespace = _object["metadata"]["namespace"]
        self.labels = _object["metadata"].get("labels", {})

    def update(self):
        logger.debug(f"Fetching object GefyraBridgeMount {self.mount_id}")
        gbm = get_gefyrabridgemount(self._config, self.mount_id)
        self._init_data(gbm)
