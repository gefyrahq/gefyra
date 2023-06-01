import random
import re
import string
from time import sleep
from collections import defaultdict
from os import path
import os
from types import MappingProxyType
from typing import Any, Dict, List, Optional, Tuple
from gefyra.connection.stowaway.resources.configmaps import (
    create_stowaway_proxyroute_configmap,
)
from gefyra.connection.stowaway.resources.services import create_stowaway_proxy_service
from gefyra.resources.events import _get_now
import kopf
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
    handle_config_configmap,
    handle_serviceaccount,
    handle_proxyroute_configmap,
    handle_stowaway_proxy_service,
    handle_stowaway_statefulset,
    handle_stowaway_nodeport_service,
    create_stowaway_statefulset,
    create_stowaway_configmap,
    remove_stowaway_configmaps,
    remove_stowaway_services,
    remove_stowaway_statefulset,
)

app = k8s.client.AppsV1Api()
core_v1_api = k8s.client.CoreV1Api()
custom_api = k8s.client.CustomObjectsApi()

STOWAWAY_LABELS = {
    "gefyra.dev/app": "stowaway",
    "gefyra.dev/role": "connection",
    "gefyra.dev/provider": "stowaway",
}

PROXY_RELOAD_COMMAND = [
    "/bin/bash",
    "generate-proxyroutes.sh",
    "/stowaway/proxyroutes/",
]

WIREGUARD_CIDR_PATTERN = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\/\d{1,3}$")


class Stowaway(AbstractGefyraConnectionProvider):
    provider_type = "stowaway"

    def __init__(
        self,
        configuration: OperatorConfiguration,
        logger,
    ):
        self.configuration = configuration
        self.logger = logger

    def install(self, config: Optional[Dict[Any, Any]] = None):
        handle_serviceaccount(self.logger, self.configuration)
        handle_proxyroute_configmap(self.logger, self.configuration)
        handle_config_configmap(self.logger, self.configuration)
        sts_stowaway = handle_stowaway_statefulset(
            self.logger, self.configuration, STOWAWAY_LABELS
        )

        handle_stowaway_nodeport_service(self.logger, self.configuration, sts_stowaway)

    def installed(self, config: Optional[Dict[Any, Any]] = None) -> bool:
        return all(
            [
                check_serviceaccount(self.logger),
                check_proxyroute_configmap(self.logger),
                check_config_configmap(self.logger),
                check_stowaway_statefulset(
                    self.logger, self.configuration, STOWAWAY_LABELS
                ),
                check_stowaway_nodeport_service(
                    self.logger,
                    create_stowaway_statefulset(STOWAWAY_LABELS, self.configuration),
                ),
            ]
        )

    def uninstall(self, config: Optional[Dict[Any, Any]] = None):
        remove_stowaway_services(self.logger, self.configuration)
        remove_stowaway_statefulset(
            self.logger,
            create_stowaway_statefulset(STOWAWAY_LABELS, self.configuration),
        )
        remove_stowaway_configmaps(self.logger, self.configuration)

    def ready(self) -> bool:
        pod = self._get_stowaway_pod()
        # check if stowaway pod is ready
        if pod and pod.status.container_statuses is not None:
            if pod.status.container_statuses[0].ready:
                return True
            else:
                return False
        else:
            return False

    def add_peer(self, peer_id: str, parameters: Optional[Dict[Any, Any]] = None):
        parameters = parameters or {}
        self.logger.info(
            f"Adding peer {peer_id} to stowaway with parameters: {parameters}"
        )
        try:
            self._edit_peer_configmap(add=peer_id, subnet=parameters.get("subnet"))
            self._restart_stowaway()
            sleep(1)
        except k8s.client.exceptions.ApiException as e:
            self.logger.error(f"Error adding peer {peer_id} to stowaway: {e}")

    def remove_peer(self, peer_id: str):
        self.logger.info(f"Removing peer {peer_id} from stowaway")
        try:
            self._edit_peer_configmap(remove=peer_id)
            pod = self._get_stowaway_pod()
            if pod is None:
                raise RuntimeError("No Stowaway Pod found for peer removal")
            exec_command_pod(
                core_v1_api,
                pod.metadata.name,
                pod.metadata.namespace,
                "stowaway",
                ["rm", "-rf", f"/config/peer_{self._translate_peer_name(peer_id)}"],
            )
            self._restart_stowaway()
            sleep(1)
            return True
        except k8s.client.exceptions.ApiException as e:
            self.logger.error(f"Error removing peer {peer_id} from stowaway: {e}")
            return False

    def peer_exists(self, peer_id: str) -> bool:
        _config = create_stowaway_configmap()
        try:
            configmap = core_v1_api.read_namespaced_config_map(
                _config.metadata.name, _config.metadata.namespace
            )
            if self._translate_peer_name(peer_id) in configmap.data["PEERS"].split(","):
                return True
            else:
                return False
        except k8s.client.exceptions.ApiException as e:
            self.logger.error(f"Error looking up peer {peer_id}: {e}")
            return False

    def get_peer_config(self, peer_id: str) -> dict[str, str]:
        if self.peer_exists(peer_id):
            return self._get_wireguard_connection_details(peer_id)
        else:
            raise RuntimeError(f"Peer {peer_id} does not exist")

    def add_destination(
        self,
        peer_id: str,
        destination_ip: str,
        destination_port: int,
        parameters: Optional[Dict[Any, Any]] = None,
    ):
        # create service with random port that is not taken
        stowaway_port = self._edit_proxyroutes_configmap(
            peer_id=peer_id, add=f"{destination_ip}:{destination_port}"
        )
        # create a stowaway proxy k8s service (target of reverse proxy in bridge operations)
        svc = handle_stowaway_proxy_service(
            self.logger,
            self.configuration,
            create_stowaway_statefulset(STOWAWAY_LABELS, self.configuration),
            stowaway_port,
            peer_id,
        )
        stowaway_pod = self._get_stowaway_pod()
        if stowaway_pod is None:
            raise RuntimeError("No Stowaway Pod found for destination addition")
        self._notify_stowaway_pod(stowaway_pod.metadata.name)
        exec_command_pod(
            core_v1_api,
            stowaway_pod.metadata.name,
            self.configuration.NAMESPACE,
            "stowaway",
            PROXY_RELOAD_COMMAND,
        )
        return f"{svc.metadata.name}.{self.configuration.NAMESPACE}.svc.cluster.local:{stowaway_port}"

    def get_destination(
        self, peer_id: str, destination_ip: str, destination_port: int
    ) -> str:
        svcs = core_v1_api.list_namespaced_service(
            namespace=self.configuration.NAMESPACE,
            label_selector=get_label_selector(
                {
                    "gefyra.dev/app": "stowaway",
                    "gefyra.dev/role": "proxy",
                    "gefyra.dev/client-id": peer_id,
                }
            ),
        )
        if len(svcs.items) == 0:
            raise RuntimeError(
                f"Error looking up destination {destination_ip}:{destination_port} for client {peer_id}: no proxy service found"
            )
        _, stowaway_port = svcs.items[0].metadata.name.rsplit("-", 1)
        return f"{svcs.items[0].metadata.name}.{self.configuration.NAMESPACE}.svc.cluster.local:{stowaway_port}"

    def remove_destination(
        self, peer_id: str, destination_ip: str, destination_port: int
    ):
        # update configmap and return the port that was removed
        stowaway_port = self._edit_proxyroutes_configmap(
            peer_id=peer_id, remove=f"{destination_ip}:{destination_port}"
        )
        proxy_svc = create_stowaway_proxy_service(
            create_stowaway_statefulset(STOWAWAY_LABELS, self.configuration),
            stowaway_port,
            client_id=peer_id,
        )
        try:
            core_v1_api.delete_namespaced_service(
                name=proxy_svc.metadata.name, namespace=proxy_svc.metadata.namespace
            )
        except k8s.client.exceptions.ApiException as e:
            if e.status != 404:
                self.logger.error(
                    f"Error removing proxy service {proxy_svc.metadata.name}: {e}"
                )
        stowaway_pod = self._get_stowaway_pod()
        if stowaway_pod is None:
            raise RuntimeError("No Stowaway Pod found for destination removal")
        self._notify_stowaway_pod(stowaway_pod.metadata.name)
        exec_command_pod(
            core_v1_api,
            stowaway_pod.metadata.name,
            self.configuration.NAMESPACE,
            "stowaway",
            PROXY_RELOAD_COMMAND,
        )

    def destination_exists(
        self, peer_id: str, destination_ip: str, destination_port: int
    ) -> bool:
        _config = create_stowaway_proxyroute_configmap()
        try:
            configmap = core_v1_api.read_namespaced_config_map(
                _config.metadata.name, _config.metadata.namespace
            )
            if configmap.data is None:
                return False
            for k, v in configmap.data.items():
                if f"{destination_ip}:{destination_port}" in v:
                    return True
            return False
        except k8s.client.exceptions.ApiException as e:
            self.logger.error(
                f"Error looking up destination {destination_ip}:{destination_port} for peer {peer_id}: {e}"
            )
            return False

    def validate(self, gclient: dict, hints: Optional[Dict[Any, Any]] = None):
        if wireguard_parameter := gclient.get("providerParameter"):
            if subnet := wireguard_parameter.get("subnet"):
                if not bool(WIREGUARD_CIDR_PATTERN.match(subnet)):
                    raise kopf.AdmissionError(
                        f"The Wireguard subnet '{subnet}' does not validate with regex '{WIREGUARD_CIDR_PATTERN}'."
                    )
                if hints.get("added") == "providerParameter" and self._subnet_taken(subnet):
                    raise kopf.AdmissionError(
                        f"The Wireguard subnet '{subnet}' is already taken."
                    )

    def _subnet_taken(self, subnet: str) -> bool:
        _config = create_stowaway_configmap()
        configmap = core_v1_api.read_namespaced_config_map(
            _config.metadata.name, _config.metadata.namespace
        )
        for k, v in configmap.data.items():
            if k.startswith("SERVER_ALLOWEDIPS_PEER_"):
                if v.split("/", 1)[0] == subnet.split("/", 1)[0]:
                    return True
            else:
                continue
        return False

    def _restart_stowaway(self) -> None:
        pod = self._get_stowaway_pod()
        if pod is None:
            raise RuntimeError("No Stowaway Pod found for restart")
        core_v1_api.delete_namespaced_pod(
            pod.metadata.name,
            pod.metadata.namespace,
            grace_period_seconds=0,
        )
        # busy wait
        _i = 0
        while (
            not self.ready()
            and _i < self.configuration.CONNECTION_PROVIDER_STARTUP_TIMEOUT
        ):
            sleep(1)
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

    def _notify_stowaway_pod(self, pod_name: str):
        self.logger.info("Notify stowaway")
        try:
            core_v1_api.patch_namespaced_pod(
                name=pod_name,
                body={
                    "metadata": {
                        "annotations": {"operator": f"update-notification-{_get_now()}"}
                    }
                },
                namespace=self.configuration.NAMESPACE,
            )
        except k8s.client.exceptions.ApiException as e:
            self.logger.exception(e)
        sleep(1)

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
        if add:
            add = self._translate_peer_name(add)
        if remove:
            remove = self._translate_peer_name(remove)
        peers = configmap.data["PEERS"].split(",")
        if add and add not in peers:
            peers = [add] + peers
            data = {"PEERS": ",".join(peers)}
            if subnet:
                data[f"SERVER_ALLOWEDIPS_PEER_{add}"] = subnet
            core_v1_api.patch_namespaced_config_map(
                name=configmap.metadata.name,
                namespace=configmap.metadata.namespace,
                body={"data": data},
            )
        if remove and remove in peers:
            peers.remove(remove)
            try:
                del configmap.data[f"SERVER_ALLOWEDIPS_PEER_{remove}"]
            except KeyError:
                pass
            configmap.data["PEERS"] = ",".join(peers)
            core_v1_api.replace_namespaced_config_map(
                name=configmap.metadata.name,
                namespace=configmap.metadata.namespace,
                body=configmap,
            )

    def _translate_peer_name(self, peer_id: str) -> str:
        return re.sub(f"[^{string.printable[:62]}]", "000", peer_id)

    def _get_free_proxyroute_port(self) -> int:
        _config = create_stowaway_proxyroute_configmap()
        configmap = core_v1_api.read_namespaced_config_map(
            _config.metadata.name, _config.metadata.namespace
        )
        routes = configmap.data
        # the values ar stored as "to_ip:to_port,proxy_port"
        if routes:
            taken_ports = [int(v.split(",")[1]) for v in routes.values()]
        else:
            taken_ports = []
        for port in range(10000, 60000):
            if port not in taken_ports:
                return port
        raise RuntimeError("No free port found for proxy route")

    def _edit_proxyroutes_configmap(
        self,
        peer_id: str,
        add: Optional[str] = None,
        remove: Optional[str] = None,
    ) -> int:
        _config = create_stowaway_proxyroute_configmap()
        configmap = core_v1_api.read_namespaced_config_map(
            _config.metadata.name, _config.metadata.namespace
        )
        routes = configmap.data
        if routes is None:
            routes = {}
        if add:
            stowaway_port = self._get_free_proxyroute_port()
            routes[
                f"{peer_id}-{''.join(random.choices(string.ascii_lowercase, k=10))}"
            ] = f"{add},{stowaway_port}"
            core_v1_api.patch_namespaced_config_map(
                name=configmap.metadata.name,
                namespace=configmap.metadata.namespace,
                body={"data": routes},
            )
            return int(stowaway_port)
        elif remove:
            to_be_deleted = None
            stowaway_port = 0
            for k, v in routes.items():
                if v.split(",")[0] == remove:
                    to_be_deleted = k
                    stowaway_port = v.split(",")[1]
            if to_be_deleted:
                del routes[to_be_deleted]
                configmap.data = routes
                core_v1_api.replace_namespaced_config_map(
                    name=configmap.metadata.name,
                    namespace=configmap.metadata.namespace,
                    body=configmap,
                )
            return int(stowaway_port)
        else:
            raise ValueError("Either the add or remove parameter must be set")

    def _get_wireguard_connection_details(self, peer_id: str) -> dict[str, str]:
        pod = self._get_stowaway_pod()
        if pod is None:
            raise RuntimeError("No Stowaway Pod found for peer lookup")
        peer_config_file = path.join(
            self.configuration.STOWAWAY_PEER_CONFIG_PATH,
            f"peer_{self._translate_peer_name(peer_id)}",
            f"peer_{self._translate_peer_name(peer_id)}.conf",
        )
        self.logger.info(
            f"Copy peer {peer_id} connection details from Pod "
            f"{pod.metadata.name}:{peer_config_file}"
        )
        tmpfile_location = f"/tmp/peer_{self._translate_peer_name(peer_id)}.conf"
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
        data: dict = defaultdict(dict)
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
