from datetime import datetime
from typing import Optional

import kubernetes as k8s
from statemachine import State, StateMachine


from gefyra.base import GefyraStateObject, StateControllerMixin
from gefyra.configuration import OperatorConfiguration
from gefyra.bridgemount.abstract import AbstractGefyraBridgeMountProvider
from gefyra.bridgemount.duplicate import DuplicateBridgeMount


class GefyraBridgeMountObject(GefyraStateObject):
    plural = "gefyrabridgemounts"


class GefyraBridgeMount(StateMachine, StateControllerMixin):
    """
    A Gefyra Bridge Mount is implemented as a state machine
    """

    kind = "GefyraBridgeMount"
    plural = "gefyrabridgemounts"

    requested = State("Bridge Mount requested", initial=True, value="REQUESTED")
    installing = State("Bridge Mount installing", value="INSTALLING")
    # preparing = State("Bridge Mount preparing", value="PREPARING")  # needed?
    active = State("Bridge Mount active", value="ACTIVE")
    removing = State("Bridge Mount removing", value="REMOVING")
    restoring = State("Bridge Mount restoring Pod", value="RESTORING")
    error = State("Bridge Mount error", value="ERROR")
    terminated = State("Bridge Mount terminated", value="TERMINATED")

    install = requested.to(installing) | error.to(installing)

    activate = installing.to(active) | active.to.itself()
    remove = active.to(removing) | error.to(removing) | removing.to.itself()
    restore = active.to(restoring) | error.to(restoring) | restoring.to.itself()
    impair = error.from_(requested, installing, active, removing, active, error)
    terminate = (
        requested.to(terminated)
        | installing.to(terminated)
        | active.to(terminated)
        | removing.to(terminated)
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
        self._bridge_mount_provider = None

    @property
    def bridge_mount_provider(self) -> AbstractGefyraBridgeMountProvider:
        """
        It creates a Gefyra shadow provider object based on the provider type
        :return: The shadow provider is being returned.
        """
        return DuplicateBridgeMount(
            self.configuration,
            self.data["targetNamespace"],
            self.data["target"],
            self.data["targetContainer"],
            self.logger,
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

    def on_install(self):
        self.bridge_mount_provider.install()

    def on_terminate(self):
        self.logger.info(f"GefyraBridgeMount '{self.object_name}' is being removed")
        self.bridge_mount_provider.uninstall()
        self.send("terminate")
