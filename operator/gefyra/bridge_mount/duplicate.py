from functools import partial
from typing import List
import uuid
from kopf import TemporaryError
import kubernetes as k8s
from kubernetes.client import (
    V1Deployment,
    V1PodList,
    V1Pod,
    ApiException,
    V1Service,
    V1ObjectMeta,
    V1ServiceSpec,
    V1Probe,
)

from gefyra.bridge_mount.abstract import AbstractGefyraBridgeMountProvider
from gefyra.configuration import OperatorConfiguration

from gefyra.bridge.carrier2.config import Carrier2Config, CarrierProbe
from gefyra.bridge_mount.utils import (
    _get_tls_from_provider_parameters,
    generate_duplicate_deployment_name,
    generate_duplicate_svc_name,
    generate_k8s_conform_name,
    get_all_probes,
    get_ports_for_deployment,
    get_upstreams_for_svc,
)
from gefyra.utils import wait_until_condition
from gefyra.bridge.carrier2.utils import read_carrier2_config

app = k8s.client.AppsV1Api()
core_v1_api = k8s.client.CoreV1Api()
custom_object_api = k8s.client.CustomObjectsApi()


class DuplicateBridgeMount(AbstractGefyraBridgeMountProvider):
    provider_type = "duplicate"

    def __init__(
        self,
        configuration: OperatorConfiguration,
        name: str,
        target_namespace: str,
        target: str,
        target_container: str,
        logger,
        **kwargs,
    ) -> None:
        self.configuration = configuration
        self.namespace = target_namespace
        self.target = target
        self.container = target_container
        self.name = name
        self.logger = logger
        self.params = kwargs.get("provider_parameter", {})

    def _get_duplication_labels(self, labels: dict[str, str]) -> dict[str, str]:
        duplication_labels = {}
        for key in labels:
            duplication_labels[key] = generate_k8s_conform_name(
                f"{labels[key]}", "-gefyra"
            )
        return duplication_labels

    def _clean_annotations(self, annotations: dict[str, str]) -> dict[str, str]:
        ANNOTATION_FILTER = [
            "kubectl.kubernetes.io/last-applied-configuration",
            "deployment.kubernetes.io/revision",
        ]
        return {
            key: value
            for key, value in annotations.items()
            if key not in ANNOTATION_FILTER
        }

    @property
    def _carrier_image(self):
        return f"{self.configuration.CARRIER2_IMAGE}:{self.configuration.CARRIER2_IMAGE_TAG}"

    @property
    def _gefyra_workload_name(self) -> str:
        return f"{self.target}-gefyra"

    def _clone_deployment_structure(self, deployment: V1Deployment) -> V1Deployment:
        new_deployment = deployment

        # Update labels to add -gefyra suffix
        labels = self._get_duplication_labels(new_deployment.metadata.labels or {})
        new_deployment.metadata.labels = labels
        new_deployment.metadata.resource_version = None
        new_deployment.metadata.uid = None

        new_deployment.metadata.name = generate_duplicate_deployment_name(
            deployment.metadata.name
        )

        pod_labels = self._get_duplication_labels(
            new_deployment.spec.template.metadata.labels or {}
        )
        # we use this for svc selector
        pod_labels["bridge.gefyra.dev/duplication-id"] = str(uuid.uuid4())
        new_deployment.spec.template.metadata.labels = pod_labels

        match_labels = self._get_duplication_labels(
            new_deployment.spec.selector.match_labels or {}
        )
        new_deployment.spec.selector.match_labels = match_labels
        new_deployment.metadata.annotations = self._clean_annotations(
            new_deployment.metadata.annotations or {}
        )
        return new_deployment

    def _get_svc_for_deployment(self, deployment: V1Deployment) -> V1Service:
        return V1Service(
            metadata=V1ObjectMeta(
                name=generate_duplicate_svc_name(
                    workload_name=self.target, container_name=self.container
                ),
                labels=deployment.metadata.labels,
            ),
            spec=V1ServiceSpec(
                selector={
                    "bridge.gefyra.dev/duplication-id": deployment.spec.template.metadata.labels[
                        "bridge.gefyra.dev/duplication-id"
                    ]
                },
                ports=get_ports_for_deployment(
                    deployment=deployment, container_name=self.container
                ),
            ),
        )

    def _duplicate_deployment(self) -> None:
        deployment = self._get_workload()

        # TODO check if deployment/svc already exists, handle with 'patch' instead of 'create'

        # Create a copy of the deployment
        new_deployment = self._clone_deployment_structure(deployment)
        new_svc = self._get_svc_for_deployment(new_deployment)

        # Create the new deployment
        app.create_namespaced_deployment(self.namespace, new_deployment)
        core_v1_api.create_namespaced_service(
            self.namespace,
            new_svc,
        )

    def _get_workload(self) -> V1Deployment:
        # TODO extend to pods
        try:
            return app.read_namespaced_deployment(self.target, self.namespace)
        except ApiException as e:
            if e.status == 404:
                raise Exception(f"Deployment {self.target} not found.")
            raise RuntimeError(f"Exception when calling Kubernetes API: {e}")

    def prepare(self):
        self._duplicate_deployment()

    @property
    def _gefyra_pods(self) -> V1PodList:
        return self._get_pods_workload(
            name=self._gefyra_workload_name,
            namespace=self.namespace,
            workload_type="deployment",
        )

    @property
    def _original_pods(self) -> V1PodList:
        return self._get_pods_workload(
            name=self.target,
            namespace=self.namespace,
            workload_type="deployment",
        )

    # TODO this also exists in the client, should be moved to a shared location
    def _get_pods_workload(
        self, name: str, namespace: str, workload_type: str
    ) -> V1PodList:
        API_EXCEPTION_MSG = "Exception when calling Kubernetes API: {}"
        NOT_FOUND_MSG = f"{workload_type.capitalize()} not found."
        try:
            if workload_type == "deployment":
                workload = app.read_namespaced_deployment(
                    name=name, namespace=namespace
                )
            elif workload_type == "statefulset":
                workload = app.read_namespaced_stateful_set(
                    name=name, namespace=namespace
                )
        except ApiException as e:
            if e.status == 404:
                # TODO better exception typing here
                raise Exception(NOT_FOUND_MSG)
            raise RuntimeError(API_EXCEPTION_MSG.format(e))

        # use workloads metadata uuid for owner references with field selector to get pods
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
    def _default_upstream(self) -> List[str]:
        svc_name = generate_duplicate_svc_name(
            workload_name=self.target, container_name=self.container
        )
        svc = core_v1_api.read_namespaced_service(svc_name, self.namespace)
        return get_upstreams_for_svc(
            svc=svc,
        )

    def _set_carrier_upstream(
        self, upstream_ports: list[int], probes: List[V1Probe]
    ) -> Carrier2Config:
        carrier_config = Carrier2Config()

        # TODO what about multiple ports?
        for upstream_port in upstream_ports:
            carrier_config.port = upstream_port  # TODO currently only last port working

        carrier_config.clusterUpstream = self._default_upstream
        if probes:
            carrier_config.probes = CarrierProbe(
                httpGet=[probe.http_get.port for probe in probes]
            )
        return carrier_config

    def _set_tls(self, carrier_config: Carrier2Config) -> Carrier2Config:
        if self.params and self.params.get("tls"):
            carrier_config.tls = _get_tls_from_provider_parameters(self.params)
        return carrier_config

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

    def install(self):
        # TODO extend to StatefulSet and Pods
        upstream_ports = []
        pods = self._original_pods.items
        if len(set(pod.metadata.owner_references[0].name for pod in pods)) > 1:
            # there is probably an update in progress
            raise TemporaryError(
                "Cannot install Gefyra Carrier2 on pods controlled by more than one controller.",
                delay=5,
            )
        for pod in pods:
            if pod.status.phase == "Terminating":
                continue
            for container in pod.spec.containers:
                upstream_ports.append(container.ports[0].container_port)
                if container.name == self.container:
                    probes = get_all_probes(container)
                    if not all(
                        map(
                            self._check_probe_compatibility,
                            probes,
                        )
                    ):
                        self.logger.error(
                            "Not all of the probes to be handled are currently"
                            " supported by Gefyra"
                        )
                        return False, pod
                    if container.image == self._carrier_image:
                        # this pod/container is already running Carrier
                        self.logger.info(
                            f"The container {self.container} in Pod {pod.metadata.name} is already"
                            " running Carrier2"
                        )
                    # self._store_pod_original_config(container)
                    container.image = self._carrier_image
                    break
            else:
                raise RuntimeError(
                    f"Could not found container {self.container} in Pod {pod}"
                )
            self.logger.info(
                f"Now patching Pod {pod.metadata.name}; container {self.container} with Carrier2"
            )
            try:
                core_v1_api.patch_namespaced_pod(
                    name=pod.metadata.name, namespace=self.namespace, body=pod
                )
            except ApiException as e:
                raise TemporaryError(
                    f"Failed to patch Pod {pod.metadata.name} with Carrier2: {e}",
                    delay=5,
                )

            # wait for the container restart to become effective
            read_func = partial(
                core_v1_api.read_namespaced_pod_status,
                pod.metadata.name,
                self.namespace,
            )
            # TODO better check for the image under s.status.container_statuses instead of restart count
            wait_until_condition(
                read_func,
                lambda s: next(
                    filter(
                        lambda c: c.name == self.container, s.status.container_statuses
                    )
                ).restart_count
                > 0,
                timeout=30,
                backoff=0.2,
            )

            carrier_config = self._set_carrier_upstream(upstream_ports, probes)
            carrier_config = self._set_tls(carrier_config)
            carrier_config.add_bridge_rules_for_mount(
                self.name, self.configuration.NAMESPACE
            )
            self.logger.info(f"Commiting carrier2 config to pod {pod.metadata.name}")
            self.logger.info(f"Carrier2 config: {carrier_config}")
            carrier_config.commit(
                pod.metadata.name,
                self.container,
                self.namespace,
            )

    @property
    def _carrier_installed(self):
        res = True
        for pod in self._original_pods.items:
            for container in pod.spec.containers:
                if container.name == self.container:
                    res = res and container.image == self._carrier_image
        return res

    def _pod_is_running(self, pod: V1Pod) -> bool:
        return pod.status.phase == "Running"

    # TODO this util exists in the client aswell and Carrier2
    # maybe refactor
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
    def _original_pods_ready(self):
        return all(
            self.pod_ready_and_healthy(pod, self.container)
            for pod in self._original_pods.items
        )

    @property
    def _duplicated_pods_ready(self):
        return all(
            self.pod_ready_and_healthy(pod, self.container)
            for pod in self._gefyra_pods.items
        )

    @property
    def _upstream_set(self) -> bool:
        for pod in self._original_pods.items:
            config_str_list = read_carrier2_config(
                core_v1_api, pod.metadata.name, self.namespace
            )
            config_str = "\n".join(config_str_list)
            pod_config = Carrier2Config.from_string(config_str)
            if not pod_config.clusterUpstream:
                return False
            return all(
                [
                    upstream in pod_config.clusterUpstream
                    for upstream in self._default_upstream
                ]
            )
        self.logger.error("Cannot determine original pods")
        return False

    def prepared(self):
        return self._duplicated_pods_ready

    def ready(self):
        return (
            self._duplicated_pods_ready
            and self._carrier_installed
            and self._original_pods_ready
            and self._upstream_set
        )

    def validate(self, brige_request):
        return super().validate(brige_request)

    def uninstall_service(self) -> None:
        gefyra_svc_name = generate_duplicate_svc_name(self.target, self.container)
        core_v1_api.delete_namespaced_service(gefyra_svc_name, self.namespace)

    def uninstall_deployment(self) -> None:
        gefyra_deployment_name = self._gefyra_workload_name
        app.delete_namespaced_deployment(gefyra_deployment_name, self.namespace)

    def uninstall(self):
        self.uninstall_deployment()
        self.uninstall_service()
