from typing import Any, Dict, Optional
import uuid
from gefyra.configuration import OperatorConfiguration
from gefyra.connection.abstract import AbstractGefyraConnectionProvider
import kubernetes as k8s
from statemachine import State

from gefyra.connection.factory import (
    ConnectionProviderType,
    connection_provider_factory,
)

from gefyra.resources.events import _get_now


class GefyraStateObject:
    plural: str

    def __init__(self, data: dict):
        self._state = None
        self.data = data
        self.name = data["metadata"]["name"]
        self.namespace = data["metadata"]["namespace"]

        self.custom_api = k8s.client.CustomObjectsApi()

    def __repr__(self):
        return f"{self.__class__.__name__}: {self.name} (state={self.state})"

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
            plural=self.plural,
            group="gefyra.dev",
            version="v1",
        )


class StateControllerMixin:
    configuration: OperatorConfiguration
    logger: Any
    custom_api: k8s.client.CustomObjectsApi
    events_api: k8s.client.EventsV1Api
    plural: str
    kind: str
    connection_provider_field: str
    data: Dict[str, Any]
    model: Any

    @property
    def object_name(self) -> str:
        """
        It returns the name of the GefyraStateObject
        :return: The name of the GefyraStateObject.
        """
        return self.model.name

    @property
    def namespace(self) -> str:
        """
        It returns the namespace of the GefyraStateObject
        :return: The name of the GefyraStateObject.
        """
        return self.data["metadata"]["namespace"]

    @property
    def connection_provider(self) -> AbstractGefyraConnectionProvider:
        """
        It creates a Gefyra connection provider object based on the connection
        provider type
        :return: The connection provider is being returned.
        """
        provider = connection_provider_factory.get(
            ConnectionProviderType(self.data.get(self.connection_provider_field)),
            self.configuration,
            self.logger,
        )
        return provider

    def completed_transition(self, target: State) -> Optional[str]:
        """
        Read the stateTransitions attribute, return the value of the
        stateTransitions timestamp for the given target, otherwise return None
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
                name=f"{self.object_name}-{uuid.uuid4()}",
                namespace=self.configuration.NAMESPACE,
            ),
            reason=reason.capitalize(),
            note=message[:1024],  # maximum message length
            event_time=now,
            action=f"{self.__class__.__name__}-State",
            type=_type,
            reporting_instance="gefyra-operator",
            reporting_controller="gefyra-operator",
            regarding=k8s.client.V1ObjectReference(
                kind=self.kind,
                name=self.object_name,
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
            name=self.object_name,
            body=data,
            group="gefyra.dev",
            plural=self.plural,
            version="v1",
        )
