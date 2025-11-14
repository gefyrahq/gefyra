from datetime import datetime
from typing import Any, Optional
from gefyra.bridge.abstract import AbstractGefyraBridgeProvider
from gefyra.bridge.factory import BridgeProviderType, bridge_provider_factory

import kopf
import kubernetes as k8s
from statemachine import State, StateMachine

from gefyra.base import GefyraStateObject, StateControllerMixin
from gefyra.configuration import OperatorConfiguration

from gefyra.bridge.exceptions import BridgeException, BridgeInstallException


class GefyraBridgeObject(GefyraStateObject):
    plural = "gefyrabridges"


class GefyraBridge(StateMachine, StateControllerMixin):
    """
    A Gefyra bridge is implemented as a state machine
    """

    kind = "GefyraBridge"
    plural = "gefyrabridges"
    connection_provider_field = "connectionProvider"

    requested = State("GefyraBridge requested", initial=True, value="REQUESTED")
    installing = State("GefyraBridge installing", value="INSTALLING")
    installed = State("GefyraBridge installed", value="INSTALLED")
    creating = State("GefyraBridge creating", value="CREATING")
    active = State("GefyraBridge active", value="ACTIVE")
    removing = State("GefyraBridge removing", value="REMOVING")
    restoring = State("GefyraBridge restoring Pod", value="RESTORING")
    error = State("GefyraBridge error", value="ERROR")
    terminating = State("GefyraBridge terminating", value="TERMINATING")

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
    remove = (
        active.to(removing)
        | error.to(removing)
        | removing.to.itself()
        | creating.to(removing)
    )
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
            self.object_name,
            self.data["targetNamespace"],
            self.data["target"],
            self.data["targetContainer"],
            self.post_event,
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
                f"Bridge '{self.object_name}' should be terminated "
                "due to reached sunset date"
            )
            return True
        else:
            return False

    def _install_provider(self):
        """
        It installs the bridge provider
        :return: Nothing
        """
        try:
            self.bridge_provider.install()
            self._wait_for_provider()
        except BridgeInstallException as be:
            self.logger.debug(f"Encountered: {be}")
            self.send("impair", exception=be)

    def _wait_for_provider(self):
        if not self.bridge_provider.ready():
            self.post_event(
                "GefyraBridge waiting",
                f"GefryaBridge '{self.object_name}' is waiting for GefyraBridge provider",
            )
            raise kopf.TemporaryError(
                (
                    "Waiting for GefyraBridge provider "
                    f"{self.bridge_provider.__class__.__name__} to become ready"
                ),
                delay=1,
            )
        else:
            self.send("set_installed")

    def on_activate(self):
        self.post_event(
            "GefyraBridge state changed",
            f"GefryaBridge '{self.object_name}' is being activated",
        )
        try:
            # TODO refactor this code
            destination = self.data["destinationIP"]
            for port_mapping in self.data.get("portMappings"):
                local_port, target_port = port_mapping.split(":")
                if not self.connection_provider.destination_exists(
                    self.data["client"], destination, int(local_port)
                ):
                    proxy_host = self.connection_provider.add_destination(
                        self.data["client"], destination, int(local_port)
                    )
                else:
                    proxy_host = self.connection_provider.get_destination(
                        self.data["client"], destination, int(local_port)
                    )
                proxy_host, proxy_port = proxy_host.split(":", 1)
                self._patch_object(
                    {"clusterEndpoint": {target_port: f"{proxy_host}:{proxy_port}"}}
                )
                self.post_event(
                    "GefyraBridge connection",
                    f"Added cluster endpoint '{proxy_host}:{proxy_port}' for local port '{local_port}'",
                )

            for port_mapping in self.data.get("portMappings"):
                local_port, target_port = port_mapping.split(":")
                proxy_host = self.connection_provider.get_destination(
                    self.data["client"], destination, int(local_port)
                )
                proxy_host, proxy_port = proxy_host.split(":", 1)
                if not self.bridge_provider.proxy_route_exists(
                    target_port, proxy_host, proxy_port
                ):
                    self.bridge_provider.add_proxy_route(
                        target_port, proxy_host, proxy_port
                    )
            self.send("establish")
        except Exception as e:
            self.send("impair", exception=e)

    def on_create(self):
        self.post_event(
            "GefyraBridge state changed",
            f"GefyraBridge '{self.object_name}' is being created",
        )

    def on_remove(self):
        self.post_event(
            "GefyraBridge state changed",
            f"GefyraBridge '{self.object_name}' is being removed",
        )
        self.send("terminate")

    def on_terminate(self):
        destination = self.data["destinationIP"]
        for port_mapping in self.data.get("portMappings"):
            source_port, target_port = port_mapping.split(":")
            if self.connection_provider.destination_exists(
                self.data["client"], destination, int(source_port)
            ):
                try:
                    proxy_host = self.connection_provider.get_destination(
                        self.data["client"], destination, int(source_port)
                    )
                except RuntimeError as e:
                    self.logger.error(
                        f"Error getting destination '{destination}' from connection provider: {e}"
                    )
                    self.connection_provider.remove_destination(
                        self.data["client"], destination, int(source_port)
                    )
                    continue
                else:
                    proxy_host, proxy_port = proxy_host.split(":", 1)
                    try:
                        if self.bridge_provider.proxy_route_exists(
                            target_port, proxy_host, proxy_port
                        ):
                            self.bridge_provider.remove_proxy_route(
                                target_port, proxy_host, proxy_port
                            )
                    except Exception as e:
                        self.logger.error(e)
                    self.connection_provider.remove_destination(
                        self.data["client"], destination, int(source_port)
                    )
            else:
                self.logger.warning(
                    f"Destination does not exist for GefyraBridge {self.object_name}: {destination}"
                )

    def on_restore(self):
        self.bridge_provider.uninstall()
        self.send("terminate")

    def on_impair(self, exception: Optional[BridgeException] = None):
        message = (
            exception.message
            if exception and hasattr(exception, "message")
            else str(exception or "")
        )
        self.post_event(
            reason=f"Failed in state {self.current_state}",
            message=message,
            type="Warning",
        )

    def on_establish(self):
        self.post_event(
            "Ready",
            f"GefyraBridge '{self.object_name}' is now active",
        )
