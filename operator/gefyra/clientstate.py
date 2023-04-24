from datetime import datetime
from typing import Any, Optional, Tuple
import uuid
import kopf
import kubernetes as k8s
from statemachine import State, StateMachine


from gefyra.configuration import OperatorConfiguration
from gefyra.connection.abstract import AbstractGefyraConnectionProvider
from gefyra.connection.factory import ProviderType, connection_provider_factory
from gefyra.resources.events import _get_now
from gefyra.resources.serviceaccounts import (
    get_serviceaccount_data,
    handle_create_gefyraclient_serviceaccount,
)


class GefyraClientObject:
    def __init__(self, data: dict):
        self._state = None
        self.data = data
        self.name = data["metadata"]["name"]
        self.namespace = data["metadata"]["namespace"]

        self.custom_api = k8s.client.CustomObjectsApi()

    def __repr__(self):
        return f"GefyraClientObject: {self.name} (state={self.state})"

    @property
    def state(self):
        if self._state is None:
            self._state = self.data["state"]
        return self._state

    @state.setter
    def state(self, value):
        self._state = value
        self._write_state(value)

    def _write_state(self, state: State):
        self.custom_api.patch_namespaced_custom_object(
            namespace=self.namespace,
            name=self.name,
            body={
                "state": str(state),
                "stateTransitions": {str(state): _get_now()},
            },
            plural="gefyraclients",
            group="gefyra.dev",
            version="v1",
        )


class GefyraClient(StateMachine):
    """
    A Gefyra client is implemented as a state machine
    """

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
        | creating.to.itself(on="create_service_account")
    )
    wait = (
        creating.to(waiting)
        | waiting.to.itself()
        | error.to(waiting)
        | disabling.to(waiting, on="on_disable")
    )
    enable = waiting.to(enabling) | error.to(enabling)
    activate = enabling.to(active, on="on_enable") | error.to(active) | active.to.itself()
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
    def connection_provider(self) -> AbstractGefyraConnectionProvider:
        """
        It creates a Gefyra connection provider object based on the provider type
        :return: The provider is being returned.
        """
        provider = connection_provider_factory.get(
            ProviderType(self.data.get("provider")),
            self.configuration,
            self.logger,
        )
        if provider is None:
            raise kopf.PermanentError(
                f"Cannot create Gefyra connection provider {self.data.get('provider')}: not supported."
            )
        return provider

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
                f"Client '{self.client_name}' should be terminated due to reached sunset date"
            )
            return True
        else:
            return False

    def on_create(self):
        self.logger.info(f"Client '{self.client_name}' is being created")

    def create_service_account(self):
        """
        This method is called when the GefyraClient is creating
        :return: None
        """
        self.logger.info(
            f"Creating service account for GefyraClient '{self.client_name}'"
        )
        sa_name = f"gefyra-client-{self.client_name}"
        handle_create_gefyraclient_serviceaccount(
            self.logger, sa_name, self.configuration.NAMESPACE
        )
        token_data = get_serviceaccount_data(sa_name, self.configuration.NAMESPACE)
        self._patch_object(
            {"serviceAccountName": sa_name, "serviceAccountToken": token_data}
        )
        self.wait()

    async def on_enable(self):
        self.logger.info(f"Client '{self.client_name}' is being enabled")
        # TODO use 'cond' instead
        if await self.connection_provider.peer_exists(self.client_name):
            raise kopf.PermanentError(
                f"Client '{self.client_name}' already exists, cannot activate it again."
            )
        self.logger.info(self.data)
        await self.connection_provider.add_peer(
            self.client_name, self.data["providerParameter"]
        )
        conn_data = await self.connection_provider.get_peer_config(self.client_name)
        self._patch_object({"providerConfig": conn_data})
        self.activate()

    async def on_disable(self):
        self.logger.info(f"Client '{self.client_name}' is being disabled")
        if await self.connection_provider.peer_exists(self.client_name):
            self.logger.warning(
                f"Client '{self.client_name}' does not exist, noting to disable."
            )
            return
        await self.connection_provider.remove_peer(self.client_name)
        self._patch_object({"providerConfig": {}, "providerParameter": {}})
        self.wait()

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
        It returns the latest state of the GefyraClient, and the timestamp of when it was in that state
        :return: A tuple of the latest state and the timestamp of the latest state.
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
                if latest_state is None:
                    latest_state = state
                    latest_timestamp = datetime.fromisoformat(timestamp.strip("Z"))  # type: ignore
                else:
                    _timestamp = datetime.fromisoformat(timestamp.strip("Z"))
                    if latest_timestamp < _timestamp:
                        latest_state = state
                        latest_timestamp = _timestamp
            return latest_state, latest_timestamp  # type: ignore
        else:
            return None

    def completed_transition(self, target: State) -> Optional[str]:
        """
        Read the stateTransitions attribute, return the value of the stateTransitions timestamp for the given
        target, otherwise return None
        :param target: The value of the state value
        :type target: State
        :return: The value of the stateTransitions key in the model dictionary.
        """
        if transitions := self.data.get("stateTransitions"):
            return transitions.get(target, None)
        else:
            return None

    def post_event(self, reason: str, message: str, _type: str = "Normal") -> None:
        """
        It creates an event object and posts it to the Kubernetes API
        :param reason: The reason for the event
        :type reason: str
        :param message: The message to be displayed in the event
        :type message: str
        :param _type: The type of event, defaults to Normal
        :type _type: str (optional)
        """
        now = _get_now()
        event = k8s.client.EventsV1Event(
            metadata=k8s.client.V1ObjectMeta(
                name=f"{self.client_name}-{uuid.uuid4()}",
                namespace=self.configuration.NAMESPACE,
            ),
            reason=reason.capitalize(),
            note=message[:1024],  # maximum message length
            event_time=now,
            action="GefyraClient-State",
            type=_type,
            reporting_instance="gefyra-operator",
            reporting_controller="gefyra-operator",
            regarding=k8s.client.V1ObjectReference(
                kind="GefyraClient",
                name=self.client_name,
                namespace=self.configuration.NAMESPACE,
                uid=self.data["metadata"]["uid"],
            ),
        )
        self.events_api.create_namespaced_event(
            namespace=self.configuration.NAMESPACE, body=event
        )

    def _patch_object(self, data: dict):
        self.custom_api.patch_namespaced_custom_object(
            namespace=self.configuration.NAMESPACE,
            name=self.client_name,
            body=data,
            group="gefyra.dev",
            plural="gefyraclients",
            version="v1",
        )
