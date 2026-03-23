from datetime import datetime
from typing import Any, Optional
from gefyra.bridge.abstract import AbstractGefyraBridgeProvider
from gefyra.bridge.factory import BridgeProviderType, bridge_provider_factory

import kopf
import kubernetes as k8s
from statemachine import State, StateChart

from gefyra.base import GefyraStateObject, StateControllerMixin
from gefyra.configuration import OperatorConfiguration

from gefyra.bridge.exceptions import BridgeException, BridgeInstallException


class GefyraBridgeObject(GefyraStateObject):
    plural = "gefyrabridges"


class GefyraBridge(StateChart, StateControllerMixin):  # Reverted to StateMachine
    """
    A Gefyra bridge is implemented as a state machine
    """

    atomic_configuration_update = True
    catch_errors_as_events = False
    enable_self_transition_entries = False
    allow_event_without_transition = False

    kind = "GefyraBridge"
    plural = "gefyrabridges"
    connection_provider_field = "connectionProvider"

    requested = State("GefyraBridge requested", initial=True, value="REQUESTED")
    installing = State("GefyraBridge installing", value="INSTALLING")
    installed = State("GefyraBridge installed", value="INSTALLED")
    creating = State("GefyraBridge creating", value="CREATING")
    active = State("GefyraBridge active", value="ACTIVE")
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
        | installing.to(installed)
        | error.to(installed)
        | installed.to.itself()
        | restoring.to(installed)
    )
    activate = installed.to(creating) | error.to(creating) | creating.to.itself()
    establish = creating.to(active) | error.to(active)
    restore = (
        installed.to(restoring)
        | error.to(restoring)
        | restoring.to.itself()
        | active.to(restoring)
    )
    impair = error.from_(requested, installing, installed, creating, active, error)
    terminate = terminating.from_(
        requested,
        restoring,
        installing,
        installed,
        creating,
        active,
        error,
        terminating,
    )

    def __init__(
        self,
        model: GefyraBridgeObject,
        configuration: OperatorConfiguration,
        logger: Any,
        initial: Optional[State] = None,
    ):
        super().__init__(start_value=initial or GefyraBridge.requested.value)
        self.model = model
        self.data = model.data
        self.operator_configuration = configuration
        self.logger = logger
        self.custom_api = k8s.client.CustomObjectsApi()
        self.events_api = k8s.client.EventsV1Api()
        self._bridge_provider = None

    @property
    async def bridge_provider(self) -> AbstractGefyraBridgeProvider:
        """
        It creates a Gefyra bridge provider object based on the provider type
        :return: The bridge provider is being returned.
        """
        provider = await bridge_provider_factory.get(
            BridgeProviderType(self.data.get("provider")),
            self.operator_configuration,
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
    async def should_terminate(self) -> bool:
        if self.sunset and self.sunset <= datetime.utcnow():
            # remove this bridge because the sunset time is in the past
            self.logger.warning(
                f"Bridge '{self.object_name}' should be terminated "
                "due to reached sunset date"
            )
            return True
        else:
            return False

    async def _install_provider(self):
        """
        It installs the bridge provider
        :return: Nothing
        """
        try:
            await (await self.bridge_provider).install()
            await self._wait_for_provider()
        except BridgeInstallException as be:
            self.logger.debug(f"Encountered: {be}")
            await self.send("impair", exception=be)

    async def _wait_for_provider(self):
        if not await (await self.bridge_provider).ready():
            await self.post_event(
                "GefyraBridge waiting",
                f"GefryaBridge '{self.object_name}' is waiting for GefyraBridge provider",
            )
            raise kopf.TemporaryError(
                (
                    "Waiting for GefyraBridge provider "
                    f"{(await self.bridge_provider).__class__.__name__} to become ready"
                ),
                delay=1,
            )
        else:
            await self.send("set_installed")

    async def on_activate(self):
        await self.post_event(
            "GefyraBridge state changed",
            f"GefryaBridge '{self.object_name}' is being activated",
        )
        try:
            destination = self.data["destinationIP"]
            await self.handle_proxyroute_setup(destination)
            await self.send("establish")
        except Exception as e:
            await self.send("impair", exception=e)

    async def handle_proxyroute_setup(self, destination):
        for port_mapping in self.data.get("portMappings"):
            local_port, target_port = port_mapping.split(":")
            if not await self.connection_provider.destination_exists(
                self.data["client"], destination, int(local_port)
            ):
                proxy_host = await self.connection_provider.add_destination(
                    self.data["client"], destination, int(local_port)
                )
            else:
                proxy_host = await self.connection_provider.get_destination(
                    self.data["client"], destination, int(local_port)
                )
            proxy_host, proxy_port = proxy_host.split(":", 1)
            await self._patch_object(
                {"clusterEndpoint": {target_port: f"{proxy_host}:{proxy_port}"}}
            )
            await self.post_event(
                "GefyraBridge connection",
                f"Added cluster endpoint '{proxy_host}:{proxy_port}' for local port '{local_port}'",
            )

        for port_mapping in self.data.get("portMappings"):
            local_port, target_port = port_mapping.split(":")
            proxy_host = await self.connection_provider.get_destination(
                self.data["client"], destination, int(local_port)
            )
            proxy_host, proxy_port = proxy_host.split(":", 1)
            if not await (await self.bridge_provider).proxy_route_exists(
                target_port, proxy_host, proxy_port, self.object_name
            ):
                await (await self.bridge_provider).add_proxy_route(
                    target_port, proxy_host, proxy_port
                )

    async def on_create(self):
        await self.post_event(
            "GefyraBridge state changed",
            f"GefyraBridge '{self.object_name}' is being created",
        )

    async def on_remove(self):
        await self.post_event(
            "GefyraBridge state changed",
            f"GefyraBridge '{self.object_name}' is being removed",
        )
        await self.send("terminate")

    async def on_terminate(self):
        destination = self.data["destinationIP"]
        await self.handle_proxyroute_teardown(destination)

    async def handle_proxyroute_teardown(self, destination):
        for port_mapping in self.data.get("portMappings"):
            source_port, target_port = port_mapping.split(":")
            if await self.connection_provider.destination_exists(
                self.data["client"], destination, int(source_port)
            ):
                try:
                    proxy_host = await self.connection_provider.get_destination(
                        self.data["client"], destination, int(source_port)
                    )
                except RuntimeError as e:
                    self.logger.error(
                        f"Error getting destination '{destination}' from connection provider: {e}"
                    )
                    await self.connection_provider.remove_destination(
                        self.data["client"], destination, int(source_port)
                    )
                    continue
                else:
                    proxy_host, proxy_port = proxy_host.split(":", 1)
                    try:
                        if await (await self.bridge_provider).proxy_route_exists(
                            target_port, proxy_host, proxy_port, self.object_name
                        ):
                            await (await self.bridge_provider).remove_proxy_route(
                                target_port, proxy_host, proxy_port
                            )
                    except Exception as e:
                        self.logger.error(e)
                    # if there is another bridge using this connetion path, we don't want to remove the route from
                    # the connection provider
                    if not await (await self.bridge_provider).proxy_route_exists(
                        target_port, proxy_host, proxy_port
                    ):
                        await self.connection_provider.remove_destination(
                            self.data["client"], destination, int(source_port)
                        )
            else:
                self.logger.warning(
                    f"Destination does not exist for GefyraBridge {self.object_name}: {destination}"
                )

    async def on_restore(self):
        await (await self.bridge_provider).uninstall()
        await self.send("set_installed")

    async def on_impair(self, exception: Optional[BridgeException] = None):
        message = (
            exception.message
            if exception and hasattr(exception, "message")
            else str(exception or "")
        )
        await self.post_event(
            reason=f"Failed in state {self.current_state}",
            message=message,
            type="Warning",
        )

    async def on_establish(self):
        await self.post_event(
            "Ready",
            f"GefyraBridge '{self.object_name}' is now active",
        )
