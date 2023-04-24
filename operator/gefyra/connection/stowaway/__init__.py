from asyncio import sleep
from collections import defaultdict
import datetime
from os import path
import os
from typing import Optional
import kubernetes as k8s

from gefyra.utils import exec_command_pod, get_label_selector, stream_copy_from_pod
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
    remove_stowaway_configmaps,
    remove_stowaway_services,
    remove_stowaway_statefulset,
)

app = k8s.client.AppsV1Api()
core_v1_api = k8s.client.CoreV1Api()

STOWAWAY_LABELS = {
    "gefyra.dev/app": "stowaway",
    "gefyra.dev/role": "connection",
    "gefyra.dev/provider": "stowaway",
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
                    create_stowaway_statefulset(STOWAWAY_LABELS, self.configuration),
                ),
                check_stowaway_rsync_service(
                    self.logger,
                    self.configuration,
                    create_stowaway_statefulset(STOWAWAY_LABELS, self.configuration),
                ),
            ]
        )

    async def uninstall(self, config: dict = {}):
        remove_stowaway_services(self.logger, self.configuration)
        remove_stowaway_statefulset(
            self.logger,
            create_stowaway_statefulset(STOWAWAY_LABELS, self.configuration),
        )
        remove_stowaway_configmaps(self.logger, self.configuration)

    async def ready(self) -> bool:
        pod = self._get_stowaway_pod()
        # check if stowaway pod is ready
        if pod and pod.status.container_statuses is not None:
            if pod.status.container_statuses[0].ready:
                return True
            else:
                return False
        else:
            return False

    async def add_peer(self, peer_id: str, parameters: dict = {}):
        self.logger.info(
            f"Adding peer {peer_id} to stowaway with parameters: {parameters}"
        )
        try:
            self._edit_peer_configmap(add=peer_id, subnet=parameters.get("subnet"))
            await self._restart_stowaway()
            await sleep(1)
            return True
        except k8s.client.exceptions.ApiException as e:
            self.logger.error(f"Error adding peer {peer_id} to stowaway: {e}")
            return False

    async def remove_peer(self, peer_id: str):
        self.logger.info(f"Removing peer {peer_id} from stowaway")
        try:
            self._edit_peer_configmap(remove=peer_id)
            pod = self._get_stowaway_pod()
            exec_command_pod(
                core_v1_api,
                pod.metadata.name,
                pod.metadata.namespace,
                "stowaway",
                ["rm", "-rf", f"/config/peer_{peer_id}"],
            )
            await self._restart_stowaway()
            await sleep(1)
            return True
        except k8s.client.exceptions.ApiException as e:
            self.logger.error(f"Error removing peer {peer_id} from stowaway: {e}")
            return False

    async def peer_exists(self, peer_id: str) -> bool:
        _config = create_stowaway_configmap()
        try:
            configmap = core_v1_api.read_namespaced_config_map(
                _config.metadata.name, _config.metadata.namespace
            )
            if peer_id in configmap.data["PEERS"].split(","):
                return True
            else:
                return False
        except k8s.client.exceptions.ApiException as e:
            self.logger.error(f"Error looking up peer {peer_id}: {e}")
            return False

    async def get_peer_config(self, peer_id: str) -> dict[str, str]:
        if await self.peer_exists(peer_id):
            return await self._get_wireguard_connection_details(peer_id)
        else:
            raise RuntimeError(f"Peer {peer_id} does not exist")

    async def add_destination(
        self, peer_id: str, destination_ip: str, destination_port: int
    ):
        raise NotImplementedError

    async def remove_destination(
        self, peer_id: str, destination_ip: str, destination_port: int
    ):
        raise NotImplementedError

    async def _restart_stowaway(self) -> None:
        pod = self._get_stowaway_pod()
        core_v1_api.delete_namespaced_pod(
            pod.metadata.name,
            pod.metadata.namespace,
            grace_period_seconds=0,
        )
        # busy wait
        _i = 0
        while (
            not await self.ready()
            and _i < self.configuration.CONNECTION_PROVIDER_STARTUP_TIMEOUT
        ):
            await sleep(1)
            _i += 1

    def _get_stowaway_pod(self) -> Optional[k8s.client.V1Pod]:
        stowaway_pod = core_v1_api.list_namespaced_pod(
            self.configuration.NAMESPACE,
            label_selector=get_label_selector(STOWAWAY_LABELS),
        )
        if stowaway_pod.items and len(stowaway_pod.items) > 0:
            return stowaway_pod.items[0]
        else:
            return None

    def _edit_peer_configmap(
        self,
        add: Optional[str] = None,
        remove: Optional[str] = None,
        subnet: Optional[str] = None,
    ) -> None:
        _config = create_stowaway_configmap()
        configmap = core_v1_api.read_namespaced_config_map(
            _config.metadata.name, _config.metadata.namespace
        )
        peers = configmap.data["PEERS"].split(",")
        if add and add not in peers:
            peers = [add] + peers
            data = {"PEERS": ",".join(peers)}
            if subnet:
                # TODO check if subnet is valid and not already in use
                data[f"SERVER_ALLOWEDIPS_PEER_{add}"] = subnet
            core_v1_api.patch_namespaced_config_map(
                name=configmap.metadata.name,
                namespace=configmap.metadata.namespace,
                body={"data": data},
            )
        if remove and remove in peers:
            peers.remove(remove)
            del configmap.data[f"SERVER_ALLOWEDIPS_PEER_{remove}"]
            configmap.data["PEERS"] = ",".join(peers)
            core_v1_api.replace_namespaced_config_map(
                name=configmap.metadata.name,
                namespace=configmap.metadata.namespace,
                body=configmap,
            )

    async def _get_wireguard_connection_details(self, peer_id: str) -> dict[str, str]:
        pod = self._get_stowaway_pod()
        peer_config_file = path.join(
            self.configuration.STOWAWAY_PEER_CONFIG_PATH,
            f"peer_{peer_id}",
            f"peer_{peer_id}.conf",
        )
        self.logger.info(
            f"Copy peer {peer_id} connection details from Pod "
            f"{pod.metadata.name}:{peer_config_file}"
        )
        tmpfile_location = f"/tmp/peer_{peer_id}.conf"
        stream_copy_from_pod(
            pod.metadata.name,
            self.configuration.NAMESPACE,
            peer_config_file,
            tmpfile_location,
        )

        # Wireguard config is unfortunately no valid TOML
        with open(tmpfile_location, "r") as f:
            peer_connection_details_raw = f.read()
        os.remove(tmpfile_location)

        peer_connection_details = self._read_wireguard_config(
            peer_connection_details_raw
        )
        return peer_connection_details

    def _read_wireguard_config(self, raw: str) -> dict[str, str]:
        """
        :param raw: the wireguard config string; similar to TOML but does not comply with
        :return: a parsed dict of the configuration
        """
        data = defaultdict(dict)
        _prefix = "none"
        for line in raw.split("\n"):
            try:
                if line.strip() == "":
                    continue
                elif "[Interface]" in line:
                    _prefix = "Interface"
                    continue
                elif "[Peer]" in line:
                    _prefix = "Peer"
                    continue
                key, value = line.split("=", 1)
                data[f"{_prefix}.{key.strip()}"] = value.strip()
            except Exception as e:
                self.logger.exception(e)
        return dict(data)


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
