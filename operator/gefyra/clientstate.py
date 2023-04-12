import datetime
from typing import Optional, Tuple
import uuid
import kopf
import kubernetes as k8s
from statemachine import State, StateMachine


from gefyra.configuration import OperatorConfiguration
from gefyra.connection.abstract import AbstractGefyraConnectionProvider
from gefyra.connection.factory import ProviderType, connection_provider_factory


class GefyraClient(StateMachine):
    """
    A Gefyra client is implemented as a state machine
    The body of the GefyraClient is available as self.model
    """

    requested = State("Client requested", initial=True, value="REQUESTED")
    creating = State("Client creating", value="CREATING")
    waiting = State("Client waiting", value="WAITING")
    active = State("Client active", value="ACTIVE")
    error = State("Client error", value="ERROR")
    terminating = State("Client terminating", value="TERMINATING")

    create = requested.to(creating) | error.to(creating)
    wait = creating.to(waiting) | error.to(waiting)
    activate = waiting.to(active) | error.to(active) | active.to.itself()
    impair = error.from_(requested, creating, waiting, active, error)
    terminate = terminating.from_(requested, creating, waiting, active, error, terminating)

    def __init__(
        self,
        configuration: OperatorConfiguration,
        model=None,
        logger=None,
    ):
        super(GefyraClient, self).__init__()
        self.model = model
        self.current_state_value = model.get("state")
        self.logger = logger
        self.configuration = configuration
        self.custom_api = k8s.client.CustomObjectsApi()
        self.core_api = k8s.client.CoreV1Api()
        self.events_api = k8s.client.EventsV1Api()

    @property
    def name(self) -> str:
        """
        It returns the name of the GefyraClient
        :return: The name of the GefyraClient.
        """
        return self.model["metadata"]["name"]

    @property
    def connection_provider(self) -> AbstractGefyraConnectionProvider:
        """
        It creates a Gefyra connection provider object based on the provider type
        :return: The provider is being returned.
        """
        provider = connection_provider_factory.get(
            ProviderType(self.model.get("provider")),
            self.configuration,
            self.name,
            self.namespace,
            self.logger,
        )
        if provider is None:
            raise kopf.PermanentError(
                f"Cannot create Gefyra connection provider {self.model.get('provider')}: not supported."
            )
        return provider

    @property
    async def kubeconfig(self) -> Optional[str]:
        """
        If the client already has a kubeconfig, use it, otherwise create a kubeconfig
        :return: The kubeconfig is being returned.
        """
        if kubeconfig := self.model.get("kubeconfig"):
            return kubeconfig
        else:
            # TODO create kubeconfig
            pass

    @property
    def sunset(self) -> Optional[datetime.datetime]:
        if sunset := self.model.get("sunset"):
            return datetime.fromisoformat(sunset.strip("Z"))
        else:
            return None

    @property
    def should_terminate(self) -> bool:
        if self.sunset and self.sunset <= datetime.utcnow():
            # remove this client because the sunset time is in the past
            self.logger.warning(
                f"Client '{self.name}' should be terminated due to reached sunset date"
            )
            return True
        else:
            return False

    def completed_transition(self, state_value: str) -> Optional[str]:
        """
        Read the stateTransitions attribute, return the value of the stateTransitions timestamp for the given
        state_value, otherwise return None
        :param state_value: The value of the state value
        :type state_value: str
        :return: The value of the stateTransitions key in the model dictionary.
        """
        if transitions := self.model.get("stateTransitions"):
            return transitions.get(state_value, None)
        else:
            return None

    def get_latest_transition(self) -> Optional[datetime.datetime]:
        """
        > Get the latest transition time for a cluster
        :return: The latest transition times
        """
        timestamps = list(
            filter(
                lambda k: k is not None,
                [
                    self.completed_transition(GefyraClient.waiting.value),
                    self.completed_transition(GefyraClient.creating.value),
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

    def get_latest_state(self) -> Optional[Tuple[str, datetime.datetime]]:
        """
        It returns the latest state of the cluster, and the timestamp of when it was in that state
        :return: A tuple of the latest state and the timestamp of the latest state.
        """
        states = list(
            filter(
                lambda k: k[1] is not None,
                {
                    GefyraClient.waiting.value: self.completed_transition(
                        GefyraClient.waiting.value
                    ),
                    GefyraClient.creating.value: self.completed_transition(
                        GefyraClient.creating.value
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

    def on_enter_requested(self) -> None:
        pass

    def _get_now(self) -> str:
        return datetime.utcnow().isoformat(timespec="microseconds") + "Z"

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
        now = self._get_now()
        event = k8s.client.EventsV1Event(
            metadata=k8s.client.V1ObjectMeta(
                name=f"{self.name}-{uuid.uuid4()}",
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
                name=self.name,
                namespace=self.configuration.NAMESPACE,
                uid=self.model.metadata["uid"],
            ),
        )
        self.events_api.create_namespaced_event(
            namespace=self.configuration.NAMESPACE, body=event
        )

    def _write_state(self):
        self.custom_api.patch_namespaced_custom_object(
            namespace=self.configuration.NAMESPACE,
            name=self.name,
            body={
                "state": self.current_state.value,
                "stateTransitions": {self.current_state.value: self._get_now()},
            },
            group="gefyra.dev",
            plural="gclients",
            version="v1",
        )

    def _patch_object(self, data: dict):
        self.custom_api.patch_namespaced_custom_object(
            namespace=self.configuration.NAMESPACE,
            name=self.name,
            body=data,
            group="gefyra.dev",
            plural="gclients",
            version="v1",
        )
