from datetime import datetime
from typing import Optional

import kubernetes as k8s
from statemachine import State, StateMachine


from gefyra.base import GefyraStateObject, StateControllerMixin
from gefyra.configuration import OperatorConfiguration
from gefyra.bridge_mount.abstract import AbstractGefyraBridgeMountProvider
from gefyra.bridge_mount.duplicate import DuplicateBridgeMount


class GefyraBridgeMountObject(GefyraStateObject):
    plural = "gefyrabridgemounts"


class GefyraBridgeMount(StateMachine, StateControllerMixin):
    """
    A Gefyra Bridge Mount is implemented as a state machine
    """

    kind = "GefyraBridgeMount"
    plural = "gefyrabridgemounts"

    requested = State("Bridge Mount requested", initial=True, value="REQUESTED")
    preparing = State("Bridge Mount preparing", value="PREPARING")
    installing = State("Bridge Mount installing", value="INSTALLING")
    active = State("Bridge Mount active", value="ACTIVE")
    restoring = State("Bridge Mount restoring workload", value="RESTORING")
    error = State("Bridge Mount error", value="ERROR")
    terminated = State("Bridge Mount terminated", value="TERMINATED")

    prepare = (
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
    impair = error.from_(requested, installing, active, active, error)
    terminate = (
        requested.to(terminated)
        | installing.to(terminated)
        | active.to(terminated)
        | restoring.to(terminated)
        | error.to(terminated)
        | terminated.to.itself()
    )

    def __init__(
        self,
        model: GefyraBridgeMountObject,
        configuration: OperatorConfiguration,
        logger,
    ):
        super().__init__()
        self.model = model
        self.data = model.data
        self.configuration = configuration
        self.logger = logger
        self.custom_api = k8s.client.CustomObjectsApi()
        self.events_api = k8s.client.EventsV1Api()
        self._bridge_mount_provider: Optional[AbstractGefyraBridgeMountProvider] = None

    @property
    def bridge_mount_provider(self) -> AbstractGefyraBridgeMountProvider:
        """
        It creates a Gefyra bridge mount provider object based on the provider type
        :return: The bridge mount provider is being returned.
        """
        return DuplicateBridgeMount(
            configuration=self.configuration,
            target_namespace=self.data["targetNamespace"],
            target=self.data["target"],
            target_container=self.data["targetContainer"],
            name=self.data["metadata"]["name"],
            logger=self.logger,
        )

    @property
    def sunset(self) -> Optional[datetime]:
        if sunset := self.data.get("sunset"):
            return datetime.fromisoformat(sunset.strip("Z"))
        else:
            return None

    @property
    def should_terminate(self) -> bool:
        if self.sunset and self.sunset <= datetime.utcnow():
            # remove this shadow because the sunset time is in the past
            self.logger.warning(
                f"Bridge Mount '{self.object_name}' should be terminated "
                "due to reached sunset date"
            )
            return True
        else:
            return False

    @property
    def is_intact(self) -> bool:
        return (
            self.bridge_mount_provider.prepared() and self.bridge_mount_provider.ready()
        )

    def on_restore(self):
        self.logger.warning(
            f"Problem detected. Restoring GefyraBridgeMount '{self.object_name}'"
        )
        if not self.bridge_mount_provider.prepared():
            self.send("prepare")
        elif not self.bridge_mount_provider.ready():
            self.send("install")

    def on_prepare(self):
        self.logger.info("Preparing GefyraBridgeMount '{self.object_name}'")
        self.bridge_mount_provider.prepare()

    @install.cond
    def _bridge_mount_prepared(self):
        return self.bridge_mount_provider.prepared()

    def on_install(self):
        self.bridge_mount_provider.install()

    @activate.cond
    def _bridge_mount_finished(self):
        return self.bridge_mount_provider.ready()

    def on_terminate(self):
        self.logger.info(f"GefyraBridgeMount '{self.object_name}' is being removed")
        self.bridge_mount_provider.uninstall()
