import kubernetes as k8s

from gefyra.utils import get_label_selector
from gefyra.connection.abstract import AbstractGefyraConnectionProvider
from gefyra.configuration import OperatorConfiguration

from .components import (
    check_proxyroute_configmap,
    check_serviceaccount,
    check_stowaway_statefulset,
    check_stowaway_nodeport_service,
    check_stowaway_rsync_service,
    handle_serviceaccount,
    handle_proxyroute_configmap,
    handle_stowaway_statefulset,
    handle_stowaway_nodeport_service,
    handle_stowaway_rsync_service,
    create_stowaway_statefulset,
)

app = k8s.client.AppsV1Api()
core_v1_api = k8s.client.CoreV1Api()

STOWAWAY_LABELS = {
    "gefyra.dev/app": "stowaway",
    "gefyra.dev/role": "connection",
    "gefyra.dev/provider": "wg",
}


class Stowaway(AbstractGefyraConnectionProvider):
    provider_type = "stowaway"

    def __init__(
        self,
        configuration: OperatorConfiguration,
        logger,
    ):
        self.configuration = configuration
        self.logger = logger

    async def install(self, config: dict = ...):
        handle_serviceaccount(self.logger, self.configuration)
        handle_proxyroute_configmap(self.logger, self.configuration)
        sts_stowaway = handle_stowaway_statefulset(
            self.logger, self.configuration, STOWAWAY_LABELS
        )

        handle_stowaway_nodeport_service(
            self.logger, self.configuration, sts_stowaway
        )
        handle_stowaway_rsync_service(
            self.logger, self.configuration, sts_stowaway
        )

    async def installed(self, config: dict = ...) -> bool:
        if all(
            [
                check_serviceaccount(self.logger, self.configuration),
                check_proxyroute_configmap(self.logger, self.configuration),
                check_stowaway_statefulset(
                    self.logger, self.configuration, STOWAWAY_LABELS
                ),
                check_stowaway_nodeport_service(
                    self.logger,
                    self.configuration,
                    create_stowaway_statefulset(STOWAWAY_LABELS),
                ),
                check_stowaway_rsync_service(
                    self.logger,
                    self.configuration,
                    create_stowaway_statefulset(STOWAWAY_LABELS),
                ),
            ]
        ):
            return True
        else:
            return False

    async def uninstall(self, config: dict = {}):
        raise NotImplementedError

    async def ready(self) -> bool:
        stowaway_pod = core_v1_api.list_namespaced_pod(
            self.configuration.NAMESPACE,
            label_selector=get_label_selector(STOWAWAY_LABELS),
        )
        # check if stowaway pod is ready
        if len(stowaway_pod.items) > 0 and stowaway_pod.items[0].status.container_statuses is not None:
            if stowaway_pod.items[0].status.container_statuses[0].ready:
                return True
            else:
                return False
        else:
            return False

    async def add_peer(self, peer_id: str):
        raise NotImplementedError

    async def remove_peer(self, peer_id: str):
        raise NotImplementedError

    async def peer_exists(self, peer_id: str) -> bool:
        raise NotImplementedError

    async def add_destination(
        self, peer_id: str, destination_ip: str, destination_port: int
    ):
        raise NotImplementedError

    async def remove_destination(
        self, peer_id: str, destination_ip: str, destination_port: int
    ):
        raise NotImplementedError


class StowawayBuilder:
    def __init__(self):
        self._instances = {}

    def __call__(
        self,
        configuration: OperatorConfiguration,
        logger,
        **_ignored,
    ):
        instance = Stowaway(
            configuration=configuration,
            logger=logger,
        )
        return instance
