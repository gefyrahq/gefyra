from datetime import datetime
import tarfile
from typing import Any, Optional, Tuple

import kopf
import kubernetes as k8s
from statemachine import State, StateMachine

from gefyra.base import GefyraStateObject, StateControllerMixin
from gefyra.configuration import OperatorConfiguration
from gefyra.resources.serviceaccounts import (
    get_serviceaccount_data,
    handle_create_gefyraclient_serviceaccount,
    handle_delete_gefyraclient_serviceaccount,
)


class GefyraClientObject(GefyraStateObject):
    plural = "gefyraclients"


class GefyraClient(StateMachine, StateControllerMixin):
    """
    A Gefyra client is implemented as a state machine
    """

    kind = "GefyraClient"
    plural = "gefyraclients"
    connection_provider_field = "provider"

    requested = State("Client requested", initial=True, value="REQUESTED")
    creating = State("Client creating", value="CREATING")
    waiting = State("Client waiting", value="WAITING")
    enabling = State("Client enabling", value="ENABLING")
    active = State("Client active", value="ACTIVE")
    disabling = State("Client disabling", value="DISABLING")
    error = State("Client error", value="ERROR")
    terminating = State("Client terminating", value="TERMINATING")

    create = (
        requested.to(creating, on="on_create")
        | error.to(creating)
        | creating.to.itself()
    )
    wait = (
        creating.to(waiting)
        | waiting.to.itself()
        | error.to(waiting)
        | disabling.to(waiting, before="disable_connection")
    )
    enable = waiting.to(enabling, cond="can_add_client") | error.to(enabling)
    activate = (
        enabling.to(active, on="enable_connection")
        | error.to(active)
        | active.to.itself()
    )
    disable = active.to(disabling) | error.to(disabling)
    impair = error.from_(requested, creating, waiting, active, error)
    terminate = terminating.from_(
        requested, creating, waiting, active, error, terminating
    )

    def __init__(
        self,
        model: GefyraClientObject,
        configuration: OperatorConfiguration,
        logger: Any,
    ):
        super().__init__()
        self.model = model
        self.data = model.data
        self.configuration = configuration
        self.logger = logger
        self.custom_api = k8s.client.CustomObjectsApi()
        self.events_api = k8s.client.EventsV1Api()
        self._connection_provider = None

    @property
    def client_name(self) -> str:
        """
        It returns the name of the GefyraClient
        :return: The name of the GefyraClient.
        """
        return self.model.name

    @property
    def namespace(self) -> str:
        """
        It returns the namespace of the GefyraClient
        :return: The name of the GefyraClient.
        """
        return self.data["metadata"]["namespace"]

    @property
    def sunset(self) -> Optional[datetime]:
        if sunset := self.data.get("sunset"):
            return datetime.fromisoformat(sunset.strip("Z"))
        else:
            return None

    @property
    def should_terminate(self) -> bool:
        if self.sunset and self.sunset <= datetime.utcnow():
            # remove this client because the sunset time is in the past
            self.logger.warning(
                f"Client '{self.object_name}' should be terminated "
                "due to reached sunset date"
            )
            return True
        else:
            return False

    def on_create(self):
        self.logger.info(f"Client '{self.object_name}' is being created")
        self.create_service_account()

    def create_service_account(self):
        """
        This method is called when the GefyraClient is creating
        :return: None
        """
        self.logger.info(
            f"Creating service account for GefyraClient '{self.object_name}'"
        )
        sa_name = f"gefyra-client-{self.object_name}"
        handle_create_gefyraclient_serviceaccount(
            self.logger, sa_name, self.configuration.NAMESPACE, self.object_name
        )
        token_data = get_serviceaccount_data(sa_name, self.configuration.NAMESPACE)
        self._patch_object(
            {"serviceAccountName": sa_name, "serviceAccountData": token_data}
        )
        self.wait()

    def on_enable(self):
        self.logger.info(f"Client '{self.object_name}' is being enabled")

    def on_activate(self):
        self.logger.info(f"Client '{self.object_name}' is being activated")

    def on_disable(self):
        self.logger.info(f"Client '{self.object_name}' is being disabled")
        self.cleanup_all_bridges()
        self.wait()

    def on_terminate(self):
        self.logger.info(f"Client '{self.object_name}' is being terminated")
        if self.connection_provider.peer_exists(self.object_name):
            self.logger.warning(
                f"Removing '{self.object_name}' from connection provider"
            )
            self.connection_provider.remove_peer(self.object_name)

        sa_name = f"gefyra-client-{self.object_name}"
        handle_delete_gefyraclient_serviceaccount(self.logger, sa_name, self.namespace)

    def can_add_client(self):
        if self.connection_provider.peer_exists(self.object_name):
            self.logger.warning(f"Client '{self.object_name}' already exists.")
            return True
        else:
            self.connection_provider.add_peer(
                self.object_name, self.data["providerParameter"]
            )
            return True

    def enable_connection(self):
        try:
            conn_data = self.connection_provider.get_peer_config(self.object_name)
        except (tarfile.ReadError, KeyError, k8s.client.rest.ApiException) as e:
            raise kopf.TemporaryError(
                f"Cannot read connection data from provider: {e}", delay=1
            )
        try:
            self._patch_object({"providerConfig": conn_data})
        except k8s.client.ApiException as e:
            if e.status == 500:
                raise kopf.TemporaryError(
                    f"Cannot enable connection: {e.reason}", delay=1
                )

    def disable_connection(self):
        try:
            if not self.connection_provider.peer_exists(self.object_name):
                self.logger.warning(
                    f"Client '{self.object_name}' does not exist, noting to disable."
                )
                return
            self.connection_provider.remove_peer(self.object_name)
        except k8s.client.rest.ApiException as e:
            if e.status == 500:
                raise kopf.TemporaryError(
                    f"Cannot disable connection: {e.reason}", delay=1
                )
        self._patch_object({"providerConfig": None})

    def cleanup_all_bridges(self):
        bridges = self.custom_api.list_namespaced_custom_object(
            group="gefyra.dev",
            version="v1",
            plural="gefyrabridges",
            namespace=self.configuration.NAMESPACE,
        )
        for bridge in bridges.get("items"):
            if bridge.get("client") == self.client_name:
                self.logger.warning(
                    "Now going to delete remaining Gefyra bridge "
                    f"'{bridge['metadata']['name']}' for client {self.client_name}"
                )
                self.custom_api.delete_namespaced_custom_object(
                    group="gefyra.dev",
                    version="v1",
                    plural="gefyrabridges",
                    namespace=self.configuration.NAMESPACE,
                    name=bridge["metadata"]["name"],
                )

    def get_latest_transition(self) -> Optional[datetime]:
        """
        > Get the latest transition time for a GefyraClient
        :return: The latest transition times
        """
        timestamps = list(
            filter(
                lambda k: k is not None,
                [
                    self.completed_transition(GefyraClient.creating.value),
                    self.completed_transition(GefyraClient.waiting.value),
                    self.completed_transition(GefyraClient.enabling.value),
                    self.completed_transition(GefyraClient.active.value),
                    self.completed_transition(GefyraClient.error.value),
                ],
            )
        )
        if timestamps:
            return max(
                map(
                    lambda x: datetime.fromisoformat(x.strip("Z")),  # type: ignore
                    timestamps,
                )
            )
        else:
            return None

    def get_latest_state(self) -> Optional[Tuple[str, datetime]]:
        """
        It returns the latest state of the GefyraClient, and the timestamp of
        when it was in that state
        :return: A tuple of the latest state and the timestamp of the latest
        state.
        """
        states = list(
            filter(
                lambda k: k[1] is not None,
                {
                    GefyraClient.creating.value: self.completed_transition(
                        GefyraClient.creating.value
                    ),
                    GefyraClient.waiting.value: self.completed_transition(
                        GefyraClient.waiting.value
                    ),
                    GefyraClient.enabling.value: self.completed_transition(
                        GefyraClient.enabling.value
                    ),
                    GefyraClient.active.value: self.completed_transition(
                        GefyraClient.active.value
                    ),
                    GefyraClient.error.value: self.completed_transition(
                        GefyraClient.error.value
                    ),
                }.items(),
            )
        )
        if states:
            latest_state, latest_timestamp = None, None
            for state, timestamp in states:
                if latest_state is None and timestamp is not None:
                    latest_state = state
                    latest_timestamp = datetime.fromisoformat(timestamp.strip("Z"))
                elif timestamp is not None:
                    _timestamp = datetime.fromisoformat(timestamp.strip("Z"))
                    if latest_timestamp and latest_timestamp < _timestamp:
                        latest_state = state
                        latest_timestamp = _timestamp
            return latest_state, latest_timestamp  # type: ignore
        else:
            return None
