import asyncio
from datetime import datetime
from typing import Optional

import kopf
import kubernetes as k8s
from statemachine import State, StateChart


from gefyra.base import GefyraStateObject, StateControllerMixin
from gefyra.configuration import OperatorConfiguration
from gefyra.bridge_mount.abstract import AbstractGefyraBridgeMountProvider
from gefyra.bridge_mount.factory import (
    BridgeMountProviderType,
    bridge_mount_provider_factory,
)
from gefyra.bridge_mount.exceptions import BridgeMountInstallException


class GefyraBridgeMountObject(GefyraStateObject):
    plural = "gefyrabridgemounts"


class GefyraBridgeMount(StateChart, StateControllerMixin):  # Reverted to StateMachine
    """
    A Gefyra Bridge Mount is implemented as a state machine
    """

    atomic_configuration_update = True
    catch_errors_as_events = False
    enable_self_transition_entries = False
    allow_event_without_transition = False

    kind = "GefyraBridgeMount"
    plural = "gefyrabridgemounts"

    requested = State("Bridge Mount requested", initial=True, value="REQUESTED")
    preparing = State("Bridge Mount preparing", value="PREPARING")
    installing = State("Bridge Mount installing", value="INSTALLING")
    active = State("Bridge Mount active", value="ACTIVE")
    restoring = State("Bridge Mount restoring workload", value="RESTORING")
    error = State("Bridge Mount error", value="ERROR")
    terminated = State("Bridge Mount terminated", value="TERMINATED")

    arrange = (
        restoring.to(preparing)
        | requested.to(preparing)
        | error.to(preparing)
        | preparing.to.itself()
    )
    install = (
        restoring.to(preparing) | preparing.to(installing) | installing.to.itself()
    )
    activate = installing.to(active) | active.to.itself()

    restore = active.to(restoring) | error.to(restoring) | restoring.to.itself()
    impair = error.from_(preparing, requested, installing, active, restoring, error)
    terminate = (
        requested.to(terminated)
        | installing.to(terminated)
        | active.to(terminated)
        | preparing.to(terminated)
        | restoring.to(terminated)
        | error.to(terminated)
        | terminated.to.itself()
    )

    def __init__(
        self,
        model: GefyraBridgeMountObject,
        configuration: OperatorConfiguration,
        logger,
        initial: Optional[State] = None,  # Added initial state parameter
    ):
        super().__init__(
            start_value=initial or GefyraBridgeMount.requested.id
        )  # Pass initial state to super
        self.model = model
        self.data = model.data
        self.operator_configuration = configuration
        self.logger = logger
        self.custom_api = k8s.client.CustomObjectsApi()
        self.events_api = k8s.client.EventsV1Api()
        self._bridge_mount_provider: Optional[AbstractGefyraBridgeMountProvider] = None

    @property
    def bridge_mount_provider(self) -> AbstractGefyraBridgeMountProvider:
        """
        It creates a GefyraBridgeMount provider object based on the provider type
        :return: The GefyraBridgeMount provider is being returned.
        """
        if self._bridge_mount_provider is None:
            self._bridge_mount_provider = bridge_mount_provider_factory.get(
                provider_type=BridgeMountProviderType(self.data["provider"]),
                configuration=self.operator_configuration,
                target_namespace=self.data["targetNamespace"],
                target=self.data["target"],
                target_container=self.data["targetContainer"],
                name=self.data["metadata"]["name"],
                post_event_function=self.post_event,
                parameter=self.data.get("providerParameter", {}),
                logger=self.logger,
            )
        return self._bridge_mount_provider

    @property
    def sunset(self) -> Optional[datetime]:
        if sunset := self.data.get("sunset"):
            return datetime.fromisoformat(sunset.strip("Z"))
        else:
            return None

    @property
    async def should_terminate(self) -> bool:  # Made async
        if self.sunset and self.sunset <= datetime.utcnow():
            # remove this shadow because the sunset time is in the past
            await self.post_event(
                reason="GefyraBridgeMount state change",
                message=f"Bridge Mount '{self.object_name}' should be terminated "
                "due to reached sunset date",
            )
            return True
        else:
            return False

    @property
    async def is_intact(self) -> bool:

        try:
            bmp = self.bridge_mount_provider
            return await bmp.prepared() and await bmp.ready()
        except Exception as e:
            await self.post_event(
                reason="Not intact",
                message=f"GefyraBridgeMount '{self.object_name}' not intact: {e}",
                type="Warning",
            )
            return False

    async def on_restore(self):
        max_attempts = self.operator_configuration.BRIDGE_MOUNT_MAX_RESTORE_ATTEMPTS
        restore_attempts = self.data.get("status", {}).get("restoreAttempts", 0) + 1
        await self._patch_object({"status": {"restoreAttempts": restore_attempts}})

        if restore_attempts >= max_attempts:
            await self.post_event(
                reason="Circuit breaker tripped",
                message=f"GefyraBridgeMount '{self.object_name}' exceeded maximum "
                f"restore attempts ({max_attempts}). Transitioning to ERROR. "
                f"This may indicate an external controller (e.g. HPA) is "
                f"continuously scaling the target workload.",
                type="Warning",
            )
            await self.send("impair")
            return

        await self.post_event(
            reason="Change detected",
            message=f"Restoring GefyraBridgeMount '{self.object_name}' "
            f"(attempt {restore_attempts}/{max_attempts})",
            type="Warning",
        )
        await self.send("arrange")

    async def on_activate(self):
        status = self.data.get("status", {})
        restore_attempts = status.get("restoreAttempts", 0)
        install_attempts = status.get("installAttempts", 0)
        if restore_attempts > 0 or install_attempts > 0:
            await self._patch_object(
                {"status": {"restoreAttempts": 0, "installAttempts": 0}}
            )

    async def on_arrange(self):
        # await self.post_event( # Await post_event
        #     reason="GefyraBridgeMount state change",
        #     message=f"GefyraBridgeMount '{self.object_name}' is being prepared",
        # )
        try:
            #  TODO self.bridge_mount_provider.check_mount_conditions()
            bmp = self.bridge_mount_provider
            await bmp.prepare()
        except (BridgeMountInstallException, ValueError) as e:
            await self.post_event(
                reason="Failed to install GefyraBridgeMount",
                message=str(e),
                type="Warning",
            )
            await self.impair()

    @install.cond
    async def _bridge_mount_prepared(self):
        bmp = self.bridge_mount_provider
        if not await bmp.prepared():
            raise kopf.TemporaryError("GefyraBridgeMount not yet prepared", delay=5)
        return True

    async def on_install(self):
        max_attempts = self.operator_configuration.BRIDGE_MOUNT_MAX_RESTORE_ATTEMPTS
        install_attempts = self.data.get("status", {}).get("installAttempts", 0) + 1
        await self._patch_object({"status": {"installAttempts": install_attempts}})

        if install_attempts >= max_attempts:
            await self.post_event(
                reason="Circuit breaker tripped",
                message=f"GefyraBridgeMount '{self.object_name}' exceeded maximum "
                f"install attempts ({max_attempts}). Transitioning to ERROR. "
                f"This may indicate an external controller (e.g. HPA) is "
                f"continuously scaling the target workload.",
                type="Warning",
            )
            await self.impair()
            return

        await self.post_event(
            reason="GefyraBridgeMount state change",
            message=f"GefyraBridgeMount '{self.object_name}' is being installed "
            f"(attempt {install_attempts}/{max_attempts})",
        )
        try:
            bmp = self.bridge_mount_provider
            await bmp.install()
            # TODO RuntimeError failed to fullfil waiting condition
        except BridgeMountInstallException as e:
            await self.post_event(
                reason="Failed to install GefyraBridgeMount",
                message=str(e),
                type="Warning",
            )
            await self.impair()
        else:
            await self.activate()

    @activate.cond
    async def _bridge_mount_finished(self):
        bmp = self.bridge_mount_provider
        _ready = await bmp.ready()
        if _ready:
            await self.post_event(
                reason="Ready",
                message=f"GefyraBridgeMount '{self.object_name}' is ready",
            )
        return _ready

    async def on_terminate(self):
        # await self.post_event( # Await post_event
        #     reason="Deleting",
        #     message=f"GefyraBridgeMount '{self.object_name}' is being removed",
        # )
        try:
            bmp = self.bridge_mount_provider
            await bmp.uninstall()
        except Exception as e:
            self.logger.error(
                f"Cannot uninstall GefyraBridgeMount '{self.object_name}' due to: {e}"
            )
        try:
            await self.cleanup_all_bridges()
        except Exception as e:
            self.logger.error(f"Cannot cleanup remaining GefyraBridges due to: {e}")

    async def cleanup_all_bridges(self) -> None:  # Made async
        bridges = await asyncio.to_thread(
            self.custom_api.list_namespaced_custom_object,
            group="gefyra.dev",
            version="v1",
            plural="gefyrabridges",
            namespace=self.operator_configuration.NAMESPACE,
            label_selector=f"gefyra.dev/bridge-mount={self.object_name}",
        )
        for bridge in bridges.get("items"):
            self.logger.warning(
                "Now going to delete remaining GefyraBridge "
                f"'{bridge['metadata']['name']}' for GefyraBridgeMount {self.object_name}"
            )
            # obj = GefyraBridgeObject(bridge)
            # GefyraBridge needs to be async, but it's not fully converted yet, so deferring async init
            # bridge_obj = GefyraBridge(obj, self.operator_configuration, self.logger)
            # await bridge_obj.post_event( # Await post_event
            #     "GefyraBridgeMount deleted",
            #     f"GefyraBridge '{bridge_obj.object_name}' will be removed since the related GefyraBridgeMount '{self.object_name}' is currently being removed",
            # )

            await asyncio.to_thread(
                self.custom_api.delete_namespaced_custom_object,
                group="gefyra.dev",
                version="v1",
                plural="gefyrabridges",
                namespace=self.operator_configuration.NAMESPACE,
                name=bridge["metadata"]["name"],
            )
