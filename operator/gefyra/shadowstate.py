from datetime import datetime
from typing import Optional

import kubernetes as k8s
from statemachine import State, StateMachine


from gefyra.base import GefyraStateObject, StateControllerMixin
from gefyra.configuration import OperatorConfiguration
from gefyra.shadow.factory import shadow_provider_factory, ShadowProviderType
from gefyra.shadow.abstract import AbstractGefyraShadowProvider


class GefyraShadowObject(GefyraStateObject):
    plural = "gefyrashadows"


class GefyraShadow(StateMachine, StateControllerMixin):
    """
    A Gefyra shadow is implemented as a state machine
    """

    kind = "GefyraShadow"
    plural = "gefyrashadows"

    requested = State("Shadow requested", initial=True, value="REQUESTED")
    installing = State("Shadow installing", value="INSTALLING")
    installed = State("Shadow installed", value="INSTALLED")
    active = State("Shadow active", value="ACTIVE")
    removing = State("Shadow removing", value="REMOVING")
    restoring = State("Shadow restoring Pod", value="RESTORING")
    error = State("Shadow error", value="ERROR")
    terminating = State("Shadow terminating", value="TERMINATING")

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
    activate = installed.to(active) | error.to(active) | active.to.itself()
    remove = active.to(removing) | error.to(removing) | removing.to.itself()
    restore = installed.to(restoring) | error.to(restoring) | restoring.to.itself()
    impair = error.from_(requested, installing, installed, removing, active, error)
    terminate = terminating.from_(
        requested,
        restoring,
        installing,
        installed,
        active,
        removing,
        error,
        terminating,
    )

    def __init__(
        self,
        model: GefyraShadowObject,
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
        self._shadow_provider = None

    @property
    def shadow_provider(self) -> AbstractGefyraShadowProvider:
        """
        It creates a Gefyra shadow provider object based on the provider type
        :return: The shadow provider is being returned.
        """
        provider = shadow_provider_factory.get(
            ShadowProviderType(self.data.get("provider")),
            self.configuration,
            self.data["targetNamespace"],
            self.data["target"],
            self.data["targetContainer"],
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
            # remove this shadow because the sunset time is in the past
            self.logger.warning(
                f"Shadow '{self.object_name}' should be terminated "
                "due to reached sunset date"
            )
            return True
        else:
            return False

    def on_install(self):
        # TODO parameters
        self.shadow_provider.install(self.data)

    def on_activate(self):
        self.logger.info(f"Gefryashadow '{self.object_name}' is being activated")
        self.send("establish")
        pass

    def on_create(self):
        self.logger.info(f"GefyraShadow '{self.object_name}' is being created")

    def on_remove(self):
        self.logger.info(f"GefyraShadow '{self.object_name}' is being removed")
        self.shadow_provider.uninstall()
        self.send("set_installed")

    def on_restore(self):
        self.shadow_provider.uninstall()
        self.send("terminate")
