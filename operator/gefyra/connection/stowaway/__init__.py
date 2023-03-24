import kubernetes as k8s

from gefyra.utils import get_label_selector
from gefyra.connection.abstract import AbstractGefyraConnectionProvider
from gefyra.configuration import OperatorConfiguration


from .components import (
    handle_serviceaccount,
    handle_proxyroute_configmap,
    handle_stowaway_deployment,
    handle_stowaway_nodeport_service,
    handle_stowaway_rsync_service,
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

    async def install(self, config: dict = ...) -> bool:
        handle_serviceaccount(self.logger, self.configuration)
        handle_proxyroute_configmap(self.logger, self.configuration)
        deployment_stowaway = handle_stowaway_deployment(
            self.logger, self.configuration, STOWAWAY_LABELS
        )

        handle_stowaway_nodeport_service(
            self.logger, self.configuration, deployment_stowaway
        )
        handle_stowaway_rsync_service(
            self.logger, self.configuration, deployment_stowaway
        )
        return True
    
    async def uninstall(self, config: dict = {}) -> bool:
        raise NotImplementedError
    
    async def ready(self) -> bool:
        return self._check_stowaway_ready()
    
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

    def _check_stowaway_ready(self):
        stowaway_pod = core_v1_api.list_namespaced_pod(
            self.configuration.NAMESPACE,
            label_selector=get_label_selector(STOWAWAY_LABELS),
        )
        # check if stowaway pod is ready
        if stowaway_pod.items[0].status.container_statuses[0].ready:
            return True
        else:
            return False

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