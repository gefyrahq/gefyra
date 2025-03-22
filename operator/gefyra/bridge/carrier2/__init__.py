from typing import Any, Dict, Optional
import kubernetes as k8s

from gefyra.bridge.abstract import AbstractGefyraBridgeProvider
from gefyra.configuration import OperatorConfiguration

from gefyra.bridge.carrier2.utils import send_carrier2_config, reload_carrier2_config
from gefyra.bridge.carrier2.config import Carrier2Config

app = k8s.client.AppsV1Api()
core_v1_api = k8s.client.CoreV1Api()
custom_object_api = k8s.client.CustomObjectsApi()

BUSYBOX_COMMAND = "/bin/busybox"
CARRIER_CONFIGURE_COMMAND_BASE = [BUSYBOX_COMMAND, "sh", "setroute.sh"]
CARRIER_CONFIGURE_PROBE_COMMAND_BASE = [BUSYBOX_COMMAND, "sh", "setprobe.sh"]
CARRIER_ORIGINAL_CONFIGMAP = "gefyra-carrier-restore-configmap"


class Carrier2(AbstractGefyraBridgeProvider):
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
        self.carrier_config = Carrier2Config()

    provider_type = "carrier2"

    def install(self, parameters: Optional[Dict[Any, Any]] = None):
        """
        Install this Gefyra bridge provider to the Kubernetes Pod
        """

        # Done by GefyraBridgeMount, hence nothing todo here
        return

    def installed(self) -> bool:
        """
        Check if this Gefyra bridge provider is properly installed
        """

        # 1. Call self.ready() (retry), return result
        self.ready()

    def ready(self) -> bool:
        """
        Check if this Gefyra bridge provider is ready for bridges
        """

        # 1. Check if Carrier2 is running in the target Pod and status accordingly,
        # raise TemporaryError otherwise (retry)
        # 2. return True
        return True

    def uninstall(self):
        """
        Uninstall this Gefyra bridge from the Kubernetes Pod
        """

        # Done by GefyraBridgeMount, nothing todo here
        return

    def add_proxy_route(
        self,
        container_port: int,
        destination_host: str,
        destination_port: int,
        parameters: Optional[Dict[Any, Any]] = None,
    ):
        """
        Add a new proxy_route to the bridge provider
        """

        # 1. Call self.ready() (retry)
        # 2. Select all currently active GefyraBridges for this target
        # 3. Construct Carrier2 config based on ref. GefyraBridgeTarget
        #    + all active bridges and the requested bridge (including rules)
        # 4. Retrive actual config from running Carrier2 instance, raise TemporaryError on error (retry)
        # 5. Compare constructed config with actual config, return result

    def add_cluster_upstream(
        self,
        destination_host: str,
        destination_port: int,
    ):
        if self.carrier_config.clusterUpstream is None:
            self.carrier_config.clusterUpstream = []
        if (
            f"{destination_host}:{destination_port}"
            not in self.carrier_config.clusterUpstream
        ):
            self.carrier_config.clusterUpstream.append(
                f"{destination_host}:{destination_port}"
            )

    def commit_config(self) -> None:
        send_carrier2_config(core_v1_api, self.pod, self.namespace, self.carrier_config)
        reload_carrier2_config(core_v1_api, self.pod, self.namespace)

    def remove_proxy_route(
        self, container_port: int, destination_host: str, destination_port: int
    ):
        """
        Remove a bridge from the bridge provider

        :param proxy_route: the proxy_route to be removed in the form of IP:PORT
        """

        # 1. Call self.ready() (retry)
        # 2. Retrive actual config to running Carrier2 instance, raise TemporaryError on error (retry)
        # 3. Remove this brige (user-id) from bridge rules
        # 4. Send edited config to running Carrier2 instance, raise TemporaryError on error (retry)
        # 5. Carrier2 graceful reload
        # 5. Return None

        raise NotImplementedError

    def proxy_route_exists(
        self, container_port: int, destination_host: str, destination_port: int
    ) -> bool:
        """
        Returns True if a proxy route exists for this port, otherwise False
        """

        # 1. Call self.ready() (retry)
        # 2. Retrive actual config to running Carrier2 instance, raise TemporaryError on error (retry)
        # 3. Check this brige (client-id) is in the config, return the result

        raise NotImplementedError

    def validate(self, brige_request: dict):
        """
        Validate the bridge request
        """

        # 1. Select all currently active GefyraBridges for this target
        # 2. Validate parameter structure
        # 3. Perform a check if these traffic matching rules are already taken
        # 4. Error if postive check, otherwise none

        raise NotImplementedError


class Carrier2Builder:
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
        instance = Carrier2(
            configuration=configuration,
            target_namespace=target_namespace,
            target_pod=target_pod,
            target_container=target_container,
            logger=logger,
        )
        return instance
