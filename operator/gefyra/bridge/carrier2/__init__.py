from functools import cached_property
from time import sleep
from typing import Any, Callable, Dict, Optional
from kopf import TemporaryError
import kopf
import kubernetes as k8s
from kubernetes.client import ApiException, V1PodList, V1Pod

from gefyra.bridge.abstract import AbstractGefyraBridgeProvider
from gefyra.configuration import OperatorConfiguration

from gefyra.bridge.carrier2.config import (
    Carrier2Config,
    Carrier2Proxy,
    CarrierProbe,
)
from gefyra.bridge_mount.utils import (
    _get_tls_from_provider_parameters,
    generate_duplicate_svc_name,
    get_all_probes,
    get_upstreams_for_svc,
)
from gefyra.bridge.carrier2.utils import read_carrier2_config

app_api = k8s.client.AppsV1Api()
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
        target: str,
        target_container: str,
        post_event_function: Callable[[str, str, str], None],
        logger,
    ) -> None:
        self.configuration = configuration

        self.bridge_mount_name = target  # BridgeMount
        _ = self._bridge_mount_resource

        self.logger = logger
        self.carrier_config = Carrier2Config()
        self.post_event = post_event_function

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
        return self.ready()

    def ready(self) -> bool:
        """
        Check if this Gefyra bridge provider is ready for bridges
        """
        if not all(
            [self.pod_ready_and_healthy(pod, self.container) for pod in self.pods.items]
        ):
            raise TemporaryError("Pods are not ready")
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
        # params not needed since carrier just updates based on all objects
        """
        Add a new proxy_route to the bridge provider
        """
        if not self.ready():
            raise RuntimeError(
                "Not able to configure Carrier in Pods. See error above."
            )
        pods = self.pods.items
        for idx, pod in enumerate(pods):
            self.post_event(
                "Updating routing rules",
                f"Now updating routing rules in Pod {pod.metadata.name} ({idx+1} of {len(pods)} Pod(s))",
            )
            self.update_carrier_config(pod)

        # 1. Call self.ready() (retry)
        # 2. Select all currently active GefyraBridges for this target
        # 3. Construct Carrier2 config based on ref. GefyraBridgeTarget
        #    + all active bridges and the requested bridge (including rules)
        # 4. Retrive actual config from running Carrier2 instance, raise TemporaryError on error (retry)
        # 5. Compare constructed config with actual config, return result

    def _set_cluster_upstream(self, config: Carrier2Config) -> Carrier2Config:
        svc = core_v1_api.read_namespaced_service(
            name=generate_duplicate_svc_name(self._bridge_mount_target, self.container),
            namespace=self.namespace,
        )
        config.clusterUpstream = get_upstreams_for_svc(
            svc=svc,
        )
        return config

    def _cluster_upstream(self, proxy: Carrier2Proxy, rport: int) -> Carrier2Proxy:
        svc = core_v1_api.read_namespaced_service(
            name=generate_duplicate_svc_name(self._bridge_mount_target, self.container),
            namespace=self.namespace,
        )
        proxy.clusterUpstream = get_upstreams_for_svc(svc=svc, rport=rport)
        return proxy

    def _tls(self, proxy: Carrier2Proxy, rport: int) -> Carrier2Proxy:
        if self._bridge_mount_provider_parameter:
            proxy.tls = _get_tls_from_provider_parameters(
                self._bridge_mount_provider_parameter, rport
            )
        return proxy

    def _set_probes(self, config: Carrier2Config, pod: V1Pod) -> Carrier2Config:
        for container in pod.spec.containers:
            if container.name == self.container:
                probes = get_all_probes(container)
                self.carrier_config.probes = CarrierProbe(
                    httpGet=[probe.http_get.port for probe in probes]
                )
        return config

    def _set_proxies(self, config: Carrier2Config, pod: V1Pod) -> Carrier2Config:
        proxies = []
        for container in pod.spec.containers:
            if container.name == self.container:
                for cport in container.ports:
                    proxy = Carrier2Proxy(port=cport.container_port)
                    proxy = self._cluster_upstream(
                        proxy=proxy, rport=cport.container_port
                    )
                    proxy = self._tls(proxy=proxy, rport=cport.container_port)
                    proxies.append(proxy)
        config.proxy = proxies
        return config

    def _set_own_ports(self, config: Carrier2Config, pod: V1Pod) -> Carrier2Config:
        for container in pod.spec.containers:
            if container.name == self.container:
                config.port = container.ports[0].container_port
        return config

    def _set_tls(self, config: Carrier2Config):
        if (
            self._bridge_mount_provider_parameter
            and "tls" in self._bridge_mount_provider_parameter
        ):
            config.tls = _get_tls_from_provider_parameters(
                self._bridge_mount_provider_parameter
            )
        return config

    def update_carrier_config(self, pod: V1Pod):
        carrier_config = Carrier2Config()
        carrier_config = self._set_proxies(carrier_config)
        carrier_config = self._set_probes(carrier_config, pod)
        carrier_config.add_bridge_rules_for_mount(
            self.bridge_mount_name, self.configuration.NAMESPACE
        )
        carrier_config.commit(
            pod_name=pod.metadata.name,
            container_name=self.container,
            namespace=self.namespace,
            debug=self.configuration.CARRIER2_DEBUG,
        )

    def _get_pods_workload(
        self, name: str, namespace: str, workload_type: str
    ) -> V1PodList:
        API_EXCEPTION_MSG = "Exception when calling Kubernetes API: {}"
        NOT_FOUND_MSG = f"{workload_type.capitalize()} not found."
        self.logger.info(f"Getting pods for {workload_type} - {name} in {namespace}")
        try:
            if workload_type == "deployment":
                workload = app_api.read_namespaced_deployment(
                    name=name, namespace=namespace
                )
            elif workload_type == "statefulset":
                workload = app_api.read_namespaced_stateful_set(
                    name=name, namespace=namespace
                )
        except ApiException as e:
            if e.status == 404:
                # TODO better exception typing here
                raise Exception(NOT_FOUND_MSG)
            raise RuntimeError(API_EXCEPTION_MSG.format(e))

        v1_label_selector = workload.spec.selector.match_labels

        label_selector = ",".join(
            [f"{key}={value}" for key, value in v1_label_selector.items()]
        )

        if not label_selector:
            # TODO better exception typing here
            raise Exception(f"No label selector set for {workload_type} - {name}.")
        pods = core_v1_api.list_namespaced_pod(
            namespace=namespace, label_selector=label_selector
        )
        return pods

    @property
    def _bridge_mount_resource(self) -> dict:
        """
        Get the bridge mount resource
        """
        bridge_mount = custom_object_api.get_namespaced_custom_object(
            "gefyra.dev",
            "v1",
            self.configuration.NAMESPACE,
            "gefyrabridgemounts",
            self.bridge_mount_name,
        )
        self.namespace = bridge_mount["targetNamespace"]
        self.container = bridge_mount["targetContainer"]
        self.target = bridge_mount["target"]
        return bridge_mount

    @cached_property
    def _bridge_mount_provider_parameter(self) -> Optional[dict]:
        """
        Get the bridge mount provider parameter
        """
        return self._bridge_mount_resource.get("providerParameter")

    @property
    def _bridge_mount_target(self) -> str:
        return self.target

    def _get_pods_from_bridge_mount(self) -> str:
        """
        Get the pods from the bridge mount
        """
        return self._get_pods_workload(
            name=self.target,
            namespace=self.namespace,
            workload_type="deployment",  # TODO
        )

    def pod_ready_and_healthy(self, pod: V1Pod, container_name: str) -> bool:
        if not pod.status.container_statuses:
            return False
        container_idx = next(
            i
            for i, container_status in enumerate(pod.status.container_statuses)
            if container_status.name == container_name
        )
        return (
            self._pod_is_running(pod)
            and pod.status.container_statuses[container_idx].ready
            and pod.status.container_statuses[container_idx].started
            and pod.status.container_statuses[container_idx].state.running
            and pod.status.container_statuses[container_idx].state.running.started_at
        )

    @property
    def pods(self) -> V1PodList:
        return self._get_pods_from_bridge_mount()

    def _pod_is_running(self, pod: V1Pod) -> bool:
        return pod.status.phase == "Running"

    def _pod_running(self, pod: V1Pod):
        timeout = self.configuration.CARRIER_RUNNING_TIMEOUT
        waiting_pod = core_v1_api.read_namespaced_pod(
            name=pod.metadata.name, namespace=self.namespace
        )
        # wait for pod to be ready
        while not self._pod_is_running(waiting_pod) and timeout > 0:
            sleep(1)
            timeout -= 1
            waiting_pod = core_v1_api.read_namespaced_pod(
                name=pod.metadata.name, namespace=self.namespace
            )
        if timeout == 0:
            raise RuntimeError(f"Pod {pod.metadata.name} did not become ready in time")
        self.logger.debug(f"Pod {pod.metadata.name} is ready")

    def remove_proxy_route(
        self, container_port: int, destination_host: str, destination_port: int
    ):
        """
        Remove a bridge from the bridge provider

        :param proxy_route: the proxy_route to be removed in the form of IP:PORT
        """
        if not self.ready():
            raise RuntimeError(
                f"Not able to configure Carrier in Pods. See error above."
            )
        for pod in self.pods.items:
            self.update_carrier_config(pod)

    def proxy_route_exists(
        self, container_port: int, destination_host: str, destination_port: int
    ) -> bool:
        """
        Returns True if a proxy route exists for this port, otherwise False
        """

        # 1. Call self.ready() (retry)
        # 2. Retrive actual config to running Carrier2 instance, raise TemporaryError on error (retry)
        # 3. Check this brige (client-id) is in the config, return the result
        try:
            pod: V1Pod = self.pods.items[0]
        except Exception as e:
            # if the deployment, pod, etc. does not exist anymore
            self.logger.error(e)
            return False
        config_str_list = read_carrier2_config(
            core_v1_api, pod.metadata.name, pod.metadata.namespace
        )
        config_str = "\n".join(config_str_list)
        pod_config = Carrier2Config.from_string(config_str)
        if not pod_config.bridges:
            return False
        self.logger.debug(f"{destination_host}:{destination_port}")

        bridge_exists = any(
            bridge.endpoint == f"{destination_host}:{destination_port}"
            for bridge in pod_config.bridges.values()
        )
        self.logger.debug(f"Bridge exists: {bridge_exists}")
        return bridge_exists
        # raise NotImplementedError

    def validate(self, bridge_request: dict, hints: dict | None):
        """
        Validate the bridge request
        """
        # check if labels set
        if (
            "labels" not in bridge_request["metadata"]
            or "gefyra.dev/bridge-mount"
            not in bridge_request["metadata"]["labels"].keys()
            or "gefyra.dev/client" not in bridge_request["metadata"]["labels"].keys()
        ):
            raise kopf.AdmissionError(
                f"The requested GefyraBridge does not set the labels 'gefyra.dev/bridge-mount' and 'gefyra.dev/client'"
            )

        try:
            bridge_mount = custom_object_api.get_namespaced_custom_object(
                "gefyra.dev",
                "v1",
                self.configuration.NAMESPACE,
                "gefyrabridgemounts",
                bridge_request["target"],
            )
        except Exception as e:
            raise kopf.AdmissionError(
                f"The target GefyraBridgeMounts does not exist or cannot be read"
            ) from None

        if bridge_mount["state"] != "ACTIVE":
            raise kopf.AdmissionError(
                f"The target GefyraBridgeMounts is not in ACTIVE state. Please try again soon."
            ) from None

        try:
            bridges = custom_object_api.list_namespaced_custom_object(
                group="gefyra.dev",
                version="v1",
                plural="gefyrabridges",
                namespace=self.configuration.NAMESPACE,
            )
        except Exception as e:
            raise kopf.AdmissionError(f"Cannot read GefyraBridges: {e}")

        for existing_bridge in bridges.get("items"):
            if (
                existing_bridge["target"] == bridge_request["target"]
                and existing_bridge["metadata"]["labels"]
                == bridge_request["metadata"]["labels"]
                and existing_bridge["destinationIP"] == bridge_request["destinationIP"]
                and existing_bridge["providerParameter"]
                == bridge_request["providerParameter"]
            ):
                raise kopf.AdmissionError(
                    f"A GefyraBridge with these target parameters already exists."
                )


class Carrier2Builder:
    def __init__(self):
        self._instances = {}

    def __call__(
        self,
        configuration: OperatorConfiguration,
        target_namespace: str,
        target: str,
        target_container: str,
        post_event_function: Callable[[str, str, str], None],
        logger,
        **_ignored,
    ):
        instance = Carrier2(
            configuration=configuration,
            target_namespace=target_namespace,
            target=target,
            target_container=target_container,
            post_event_function=post_event_function,
            logger=logger,
        )
        return instance
