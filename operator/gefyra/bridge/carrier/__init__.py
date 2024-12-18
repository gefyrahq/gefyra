import json
from typing import Any, Dict, List, Optional
from gefyra.bridge.exceptions import BridgeInstallException
from gefyra.utils import exec_command_pod
import kubernetes as k8s

from gefyra.bridge.abstract import AbstractGefyraBridgeProvider
from gefyra.configuration import OperatorConfiguration

app = k8s.client.AppsV1Api()
core_v1_api = k8s.client.CoreV1Api()
custom_object_api = k8s.client.CustomObjectsApi()

BUSYBOX_COMMAND = "/bin/busybox"
CARRIER_CONFIGURE_COMMAND_BASE = [BUSYBOX_COMMAND, "sh", "setroute.sh"]
CARRIER_CONFIGURE_PROBE_COMMAND_BASE = [BUSYBOX_COMMAND, "sh", "setprobe.sh"]
CARRIER_ORIGINAL_CONFIGMAP = "gefyra-carrier-restore-configmap"


class Carrier(AbstractGefyraBridgeProvider):
    def __init__(
        self,
        configuration: OperatorConfiguration,
        target_namespace: str,
        target_pod: str,
        target_container: str,
        logger,
    ) -> None:
        self.configuration = configuration
        self.namespace = target_namespace
        self.pod = target_pod
        self.container = target_container
        self.logger = logger

    def install(self, parameters: Optional[Dict[Any, Any]] = None):
        parameters = parameters or {}
        self._patch_pod_with_carrier(handle_probes=parameters.get("handleProbes", True))

    def _ensure_probes(self, container: k8s.client.V1Container) -> bool:
        probes = self._get_all_probes(container)
        for probe in probes:
            try:
                command = CARRIER_CONFIGURE_PROBE_COMMAND_BASE + [
                    probe.http_get.port,
                ]
                exec_command_pod(
                    core_v1_api, self.pod, self.namespace, self.container, command
                )
            except Exception as e:
                self.logger.error(e)
                return False
        return True

    def installed(self) -> bool:
        pod = core_v1_api.read_namespaced_pod(name=self.pod, namespace=self.namespace)
        for container in pod.spec.containers:
            if (
                container.name == self.container
                and container.image
                == f"{self.configuration.CARRIER_IMAGE}:{self.configuration.CARRIER_IMAGE_TAG}"
            ):
                # we always handle probes, flag is currently ignored
                return self._ensure_probes(container=container)
        return False

    def ready(self) -> bool:
        if self.installed():
            pod = core_v1_api.read_namespaced_pod(
                name=self.pod, namespace=self.namespace
            )
            return all(
                status.ready for status in pod.status.container_statuses
            ) and any(
                f"{self.configuration.CARRIER_IMAGE}:{self.configuration.CARRIER_IMAGE_TAG}"
                in status.image
                for status in pod.status.container_statuses
            )
        else:
            return False

    def uninstall(self):
        self._patch_pod_with_original_config()

    def add_proxy_route(
        self,
        container_port: int,
        destination_host: str,
        destination_port: int,
        parameters: Optional[Dict[Any, Any]] = None,
    ):
        self._configure_carrier(container_port, destination_host, destination_port)

    def remove_proxy_route(
        self, container_port: int, destination_host: str, destination_port: int
    ):
        """This feature is currently not support by Carrier and does nothing"""
        pass

    def proxy_route_exists(
        self, container_port: int, destination_host: str, destination_port: int
    ) -> bool:
        output = exec_command_pod(
            core_v1_api,
            self.pod,
            self.namespace,
            self.container,
            ["cat", "/tmp/nginx.conf"],
        )
        if (
            f"upstream stowaway-{container_port} {{server"
            f" {destination_host}:{destination_port};}} server {{listen"
            f" {container_port}; proxy_pass stowaway-{container_port};}}" in output
        ):
            return True
        else:
            return False

    def validate(self, brige_request: Optional[Dict[Any, Any]] = None):
        raise NotImplementedError

    def _patch_pod_with_carrier(
        self,
        handle_probes: bool,
    ):
        """
        Install Gefyra Carrier to the target Pod
        :param pod_name: the name of the Pod to be patched with Carrier
        :param handle_probes: See if Gefyra can handle probes of this Pod
        """

        pod = core_v1_api.read_namespaced_pod(name=self.pod, namespace=self.namespace)

        for container in pod.spec.containers:
            if container.name == self.container:
                if handle_probes:
                    # check if these probes are all supported
                    if not all(
                        map(
                            self._check_probe_compatibility,
                            self._get_all_probes(container),
                        )
                    ):
                        raise BridgeInstallException(
                            message="Not all of the probes to be handled are currently supported by Gefyra"
                        )
                if (
                    container.image
                    == f"{self.configuration.CARRIER_IMAGE}:{self.configuration.CARRIER_IMAGE_TAG}"
                ):
                    # this pod/container is already running Carrier
                    self.logger.info(
                        f"The container {self.container} in Pod {self.pod} is already"
                        " running Carrier"
                    )
                self._store_pod_original_config(container)
                container.image = f"{self.configuration.CARRIER_IMAGE}:{self.configuration.CARRIER_IMAGE_TAG}"
                break
        else:
            raise BridgeInstallException(
                message=f"Could not found container {self.container} in Pod {self.pod}"
            )
        self.logger.info(
            f"Now patching Pod {self.pod}; container {self.container} with Carrier"
        )
        core_v1_api.patch_namespaced_pod(
            name=self.pod, namespace=self.namespace, body=pod
        )

    def _get_all_probes(
        self, container: k8s.client.V1Container
    ) -> List[k8s.client.V1Probe]:
        probes = []
        if container.startup_probe:
            probes.append(container.startup_probe)
        if container.readiness_probe:
            probes.append(container.readiness_probe)
        if container.liveness_probe:
            probes.append(container.liveness_probe)
        return probes

    def _patch_pod_with_original_config(self):
        pod = core_v1_api.read_namespaced_pod(name=self.pod, namespace=self.namespace)
        configmap = core_v1_api.read_namespaced_config_map(
            name=CARRIER_ORIGINAL_CONFIGMAP,
            namespace=self.configuration.NAMESPACE,
        )
        data = json.loads(configmap.data.get(f"{self.namespace}-{self.pod}"))

        for container in pod.spec.containers:
            if container.name == self.container:
                for k, v in data.get("originalConfig").items():
                    setattr(container, k, v)
                break
        else:
            raise RuntimeError(
                f"Could not found container {self.container} in Pod {self.pod}: cannot"
                " patch with original state"
            )

        self.logger.info(
            f"Now patching Pod {self.pod}; container {self.container} with original"
            " state"
        )
        core_v1_api.patch_namespaced_pod(
            name=self.pod, namespace=self.namespace, body=pod
        )

    def _check_probe_compatibility(self, probe: k8s.client.V1Probe) -> bool:
        """
        Check if this type of probe is compatible with Gefyra Carrier
        :param probe: instance of k8s.client.V1Probe
        :return: bool if this is compatible
        """
        if probe is None:
            return True
        elif probe._exec:
            # exec is not supported
            return False
        elif probe.tcp_socket:
            # tcp sockets are not yet supported
            return False
        elif probe.http_get:
            return True
        else:
            return True

    def _store_pod_original_config(self, container: k8s.client.V1Container) -> None:
        """
        Store the original configuration of that Container in order to restore it once the intercept request is ended
        :param container: V1Container of the Pod in question
        :param ireq_object: the InterceptRequest object
        :return: None
        """
        data = json.dumps(
            {
                "originalConfig": {
                    "image": container.image,
                    "command": container.command,
                    "args": container.args,
                }
            }
        )
        config = [
            {"op": "add", "path": f"/data/{self.namespace}-{self.pod}", "value": data}
        ]
        try:
            core_v1_api.patch_namespaced_config_map(
                name=CARRIER_ORIGINAL_CONFIGMAP,
                namespace=self.configuration.NAMESPACE,
                body=config,
            )
        except k8s.client.exceptions.ApiException as e:
            if e.status == 404:
                core_v1_api.create_namespaced_config_map(
                    namespace=self.configuration.NAMESPACE,
                    body=k8s.client.V1ConfigMap(
                        metadata=k8s.client.V1ObjectMeta(
                            name=CARRIER_ORIGINAL_CONFIGMAP
                        ),
                        data={
                            f"{self.namespace}-{self.pod}": data,
                        },
                    ),
                )
            else:
                raise e

    def _configure_carrier(
        self,
        container_port: int,
        destination_host: str,
        destination_port: int,
    ):
        if not self.ready():
            raise RuntimeError(
                f"Not able to configure Carrier in Pod {self.pod}. See error above."
            )
        try:
            command = CARRIER_CONFIGURE_COMMAND_BASE + [
                f"{container_port}",
                f"{destination_host}:{destination_port}",
            ]
            exec_command_pod(
                core_v1_api, self.pod, self.namespace, self.container, command
            )
        except Exception as e:
            self.logger.error(e)
            return
        self.logger.info(f"Carrier configured in {self.pod}")


class CarrierBuilder:
    def __init__(self):
        self._instances = {}

    def __call__(
        self,
        configuration: OperatorConfiguration,
        target_namespace: str,
        target_pod: str,
        target_container: str,
        logger,
        **_ignored,
    ):
        instance = Carrier(
            configuration=configuration,
            target_namespace=target_namespace,
            target_pod=target_pod,
            target_container=target_container,
            logger=logger,
        )
        return instance
