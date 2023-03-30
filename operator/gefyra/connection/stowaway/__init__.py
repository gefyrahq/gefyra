from asyncio import sleep
import datetime
from typing import Optional
import kubernetes as k8s

from gefyra.utils import exec_command_pod, get_label_selector
from gefyra.connection.abstract import AbstractGefyraConnectionProvider
from gefyra.configuration import OperatorConfiguration

from .components import (
    check_config_configmap,
    check_proxyroute_configmap,
    check_serviceaccount,
    check_stowaway_statefulset,
    check_stowaway_nodeport_service,
    check_stowaway_rsync_service,
    handle_config_configmap,
    handle_serviceaccount,
    handle_proxyroute_configmap,
    handle_stowaway_statefulset,
    handle_stowaway_nodeport_service,
    handle_stowaway_rsync_service,
    create_stowaway_statefulset,
    create_stowaway_configmap,
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
        handle_config_configmap(self.logger, self.configuration)
        sts_stowaway = handle_stowaway_statefulset(
            self.logger, self.configuration, STOWAWAY_LABELS
        )

        handle_stowaway_nodeport_service(self.logger, self.configuration, sts_stowaway)
        handle_stowaway_rsync_service(self.logger, self.configuration, sts_stowaway)

    async def installed(self, config: dict = ...) -> bool:
        return all(
            [
                check_serviceaccount(self.logger, self.configuration),
                check_proxyroute_configmap(self.logger, self.configuration),
                check_config_configmap(self.logger, self.configuration),
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
        )

    async def uninstall(self, config: dict = {}):
        raise NotImplementedError

    async def ready(self) -> bool:
        pod = self._get_stowaway_pod()
        # check if stowaway pod is ready
        if (
            pod
            and pod.status.container_statuses is not None
        ):
            if pod.status.container_statuses[0].ready:
                return True
            else:
                return False
        else:
            return False

    async def add_peer(self, peer_id: str):
        self.logger.info(f"Adding peer {peer_id} to stowaway")
        _config = create_stowaway_configmap()
        try:
            configmap = core_v1_api.read_namespaced_config_map(
                _config.metadata.name, _config.metadata.namespace
            )
            core_v1_api.patch_namespaced_config_map(
                name=configmap.metadata.name,
                namespace=configmap.metadata.namespace,
                body={"data":{"PEERS": ",".join([peer_id] + configmap.data["PEERS"].split(","))}},
            )
            pod = self._get_stowaway_pod()
            core_v1_api.delete_namespaced_pod(
                pod.metadata.name,
                pod.metadata.namespace,
                grace_period_seconds=0,
            )
            # busy wait
            _i = 0
            while not await self.ready() and _i < self.configuration.CONNECTION_PROVIDER_STARTUP_TIMEOUT:
                await sleep(1)
                _i += 1

            return True
        except k8s.client.exceptions.ApiException as e:
            self.logger.error(f"Error adding peer {peer_id} to stowaway: {e}")
            if e.status == 404:
                return False
            else:
                raise e

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
    
    def _get_stowaway_pod(self) -> Optional[k8s.client.V1Pod]:
        stowaway_pod = core_v1_api.list_namespaced_pod(
            self.configuration.NAMESPACE,
            label_selector=get_label_selector(STOWAWAY_LABELS),
        )
        if stowaway_pod.items and len(stowaway_pod.items) > 0:
            return stowaway_pod.items[0]
        else:
            return None
    

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
