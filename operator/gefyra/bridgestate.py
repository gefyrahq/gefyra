from datetime import datetime
import tarfile
from typing import Any, Optional, Tuple
import uuid
from gefyra.bridge.abstract import AbstractGefyraBridgeProvider
from gefyra.bridge.factory import BridgeProviderType, bridge_provider_factory

import kopf
import kubernetes as k8s
from statemachine import State, StateMachine


from gefyra.base import GefyraStateObject, StateControllerMixin
from gefyra.configuration import OperatorConfiguration
from gefyra.resources.events import _get_now


class GefyraBridgeObject(GefyraStateObject):
    plural = "gefyrabridges"


class GefyraBridge(StateMachine, StateControllerMixin):
    """
    A Gefyra bridge is implemented as a state machine
    """

    kind = "GefyraBridge"
    plural = "gefyrabridges"
    connection_provider_field = "connectionProvider"

    requested = State("Bridge requested", initial=True, value="REQUESTED")
    installing = State("Bridge installing", value="INSTALLING")
    installed = State("Bridge installed", value="INSTALLED")
    creating = State("Bridge creating", value="CREATING")
    active = State("Bridge active", value="ACTIVE")
    removing = State("Bridge removing", value="REMOVING")
    restoring = State("Bridge restoring Pod", value="RESTORING")
    error = State("Bridge error", value="ERROR")
    terminating = State("Bridge terminating", value="TERMINATING")

    install = (
        requested.to(installing, on="_install_provider")
        | error.to(installing)
        | installing.to.itself(on="_wait_for_provider")
    )
    set_installed = (
        requested.to(installed)
        | removing.to(installed)
        | installing.to(installed)
        | error.to(installed)
        | installed.to.itself()
    )
    activate = installed.to(creating) | error.to(creating) | creating.to.itself()
    establish = creating.to(active) | error.to(active)
    remove = active.to(removing) | error.to(removing) | removing.to.itself()
    restore = installed.to(restoring) | error.to(restoring) | restoring.to.itself()
    impair = error.from_(
        requested, installing, installed, creating, removing, active, error
    )
    terminate = terminating.from_(
        requested,
        restoring,
        installing,
        installed,
        creating,
        active,
        removing,
        error,
        terminating,
    )

    def __init__(
        self,
        model: GefyraBridgeObject,
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
        self._bridge_provider = None

    @property
    def bridge_provider(self) -> AbstractGefyraBridgeProvider:
        """
        It creates a Gefyra bridge provider object based on the provider type
        :return: The bridge provider is being returned.
        """
        provider = bridge_provider_factory.get(
            BridgeProviderType(self.data.get("provider")),
            self.configuration,
            self.data.get("targetNamespace"),
            self.data.get("targetPod"),
            self.data.get("targetContainer"),
            self.logger,
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
            # remove this bridge because the sunset time is in the past
            self.logger.warning(
                f"Bridge '{self.object_name}' should be terminated due to reached sunset date"
            )
            return True
        else:
            return False

    def _install_provider(self):
        """
        It installs the bridge provider
        :return: Nothing
        """
        self.bridge_provider.install()

    def _wait_for_provider(self):
        if not self.bridge_provider.ready():
            # TODO add timeout
            raise kopf.TemporaryError(
                f"Waiting for Gefyra bridge provider {self.bridge_provider.__class__.__name__} to become ready",
                delay=1,
            )
        else:
            self.send("set_installed")

    def on_activate(self):
        self.logger.info(f"GefryaBridge '{self.object_name}' is being activated")
        destination = self.data["destinationIP"]
        for port_mapping in self.data.get("portMappings"):
            source_port, target_port = port_mapping.split(":")
            if not self.connection_provider.destination_exists(
                self.data["client"], destination, int(source_port)
            ):
                proxy_host = self.connection_provider.add_destination(
                    self.data["client"], destination, int(source_port)
                )
            else:
                proxy_host = self.connection_provider.get_destination(
                    self.data["client"], destination, int(source_port)
                )
            proxy_host, proxy_port = proxy_host.split(":", 1)
            if not self.bridge_provider.proxy_route_exists(
                target_port, proxy_host, proxy_port
            ):
                self.bridge_provider.add_proxy_route(
                    target_port, proxy_host, proxy_port
                )
        self.send("establish")

    def on_create(self):
        self.logger.info(f"GefyraBridge '{self.object_name}' is being created")

    def on_remove(self):
        self.logger.info(f"GefyraBridge '{self.object_name}' is being removed")
        destination = self.data["destinationIP"]
        for port_mapping in self.data.get("portMappings"):
            source_port, target_port = port_mapping.split(":")
            if self.connection_provider.destination_exists(
                self.data["client"], destination, int(source_port)
            ):
                proxy_host = self.connection_provider.get_destination(
                    self.data["client"], destination, int(source_port)
                )
                proxy_host, proxy_port = proxy_host.split(":", 1)
                if self.bridge_provider.proxy_route_exists(
                    target_port, proxy_host, proxy_port
                ):
                    self.bridge_provider.remove_proxy_route(
                        target_port, proxy_host, proxy_port
                    )
                self.connection_provider.remove_destination(
                    self.data["client"], destination, int(source_port)
                )
        self.send("set_installed")

    def on_restore(self):
        self.bridge_provider.uninstall()
        self.send("terminate")

    def on_terminate(self):
        pass

    def get_latest_transition(self) -> Optional[datetime]:
        """
        > Get the latest transition time for a GefyraBridge
        :return: The latest transition times
        """
        timestamps = list(
            filter(
                lambda k: k is not None,
                [
                    self.completed_transition(GefyraBridge.creating.value),
                    self.completed_transition(GefyraBridge.active.value),
                    self.completed_transition(GefyraBridge.error.value),
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
        It returns the latest state of the GefyraBridge, and the timestamp of when it was in that state
        :return: A tuple of the latest state and the timestamp of the latest state.
        """
        states = list(
            filter(
                lambda k: k[1] is not None,
                {
                    GefyraBridge.creating.value: self.completed_transition(
                        GefyraBridge.creating.value
                    ),
                    GefyraBridge.active.value: self.completed_transition(
                        GefyraBridge.active.value
                    ),
                    GefyraBridge.error.value: self.completed_transition(
                        GefyraBridge.error.value
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
