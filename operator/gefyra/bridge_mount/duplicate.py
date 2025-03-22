from functools import cached_property
from time import sleep
import uuid
import kubernetes as k8s
from kubernetes.client import (
    V1Deployment,
    V1PodList,
    V1Pod,
    ApiException,
    V1Service,
    V1ObjectMeta,
    V1ServiceSpec,
    V1ServicePort,
    V1Container,
)

from gefyra.bridge_mount.abstract import AbstractGefyraBridgeMountProvider
from gefyra.configuration import OperatorConfiguration

from gefyra.bridge.carrier2 import Carrier2

app = k8s.client.AppsV1Api()
core_v1_api = k8s.client.CoreV1Api()
custom_object_api = k8s.client.CustomObjectsApi()


class DuplicateBridgeMount(AbstractGefyraBridgeMountProvider):
    provider_type = "duplicate"

    def __init__(
        self,
        configuration: OperatorConfiguration,
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
        self.logger = logger

    def _get_duplication_labels(self, labels: dict[str, str]) -> dict[str, str]:
        duplication_labels = {}
        for key in labels:
            duplication_labels[key] = f"{labels[key]}-gefyra"
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
        new_deployment.metadata.name = f"{deployment.metadata.name}-gefyra"

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

    def _get_svc_ports(self, deployment: V1Deployment) -> list[V1ServicePort]:
        ports = []
        for container in deployment.spec.template.spec.containers:
            if container.name == self.container:
                for port in container.ports:
                    ports.append(
                        V1ServicePort(
                            port=port.container_port,
                            target_port=port.container_port,
                        )
                    )
        return ports

    def _get_duplication_svc_name(self) -> str:
        return f"{self.target}-{self.container}-gefyra-svc"

    def _get_svc_for_deployment(self, deployment: V1Deployment) -> V1Service:
        return V1Service(
            metadata=V1ObjectMeta(
                name=self._get_duplication_svc_name(),
                labels=deployment.metadata.labels,
            ),
            spec=V1ServiceSpec(
                selector={
                    "bridge.gefyra.dev/duplication-id": deployment.spec.template.metadata.labels[
                        "bridge.gefyra.dev/duplication-id"
                    ]
                },
                ports=self._get_svc_ports(deployment=deployment),
            ),
        )

    def _duplicate_deployment(self, deployment_name: str, namespace: str) -> None:
        deployment = app.read_namespaced_deployment(deployment_name, namespace)

        # Create a copy of the deployment
        new_deployment = self._clone_deployment_structure(deployment)
        new_svc = self._get_svc_for_deployment(new_deployment)

        # Create the new deployment
        app.create_namespaced_deployment(namespace, new_deployment)
        core_v1_api.create_namespaced_service(
            namespace,
            new_svc,
        )

    def prepare(self):
        self._duplicate_deployment(self.target, self.namespace)

    @cached_property
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

    def _get_svc_fqdn(self) -> str:
        svc_name = self._get_duplication_svc_name()
        return f"{svc_name}.{self.namespace}.svc.cluster.local"

    def _set_carrier_upstream(self, pod: V1Pod, container: V1Container) -> None:
        timeout = 30
        waiting_pod = core_v1_api.read_namespaced_pod(
            name=pod.metadata.name, namespace=self.namespace
        )
        # wait for pod to be ready
        while (
            not self.pod_ready_and_healthy(waiting_pod, self.container) and timeout > 0
        ):
            sleep(1)
            timeout -= 1
            waiting_pod = core_v1_api.read_namespaced_pod(
                name=pod.metadata.name, namespace=self.namespace
            )
        if timeout == 0:
            raise RuntimeError(f"Pod {pod.metadata.name} did not become ready in time")
        carrier = Carrier2(
            configuration=self.configuration,
            target_namespace=self.namespace,
            target_pod=pod.metadata.name,
            target_container=self.container,
            logger=self.logger,
        )
        for port in container.ports:
            carrier.add_cluster_upstream(
                container_port=port.container_port,
                destination_host=self._get_svc_fqdn(),
                destination_port=port.container_port,
            )

    def install(self):
        # TODO extend to StatefulSet and Pods
        for pod in self._original_pods.items:
            for container in pod.spec.containers:
                if container.name == self.container:
                    # TODO
                    # if self.handle_probes:
                    #     # check if these probes are all supported
                    #     if not all(
                    #         map(
                    #             self._check_probe_compatibility,
                    #             self._get_all_probes(container),
                    #         )
                    #     ):
                    #         self.logger.error(
                    #             "Not all of the probes to be handled are currently"
                    #             " supported by Gefyra"
                    #         )
                    #         return False, pod)
                    if container.image == self._carrier_image:
                        # this pod/container is already running Carrier
                        self.logger.info(
                            f"The container {self.container} in Pod {pod} is already"
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
            core_v1_api.patch_namespaced_pod(
                name=pod.metadata.name, namespace=self.namespace, body=pod
            )
            self._set_carrier_upstream(pod, container)

    @property
    def _carrier_installed(self):
        res = True
        for pod in self._original_pods.items:
            for container in pod.spec.containers:
                if container.name == self.container:
                    res = res and container.image == self._carrier_image
        return res

    # TODO this util exists in the client aswell
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
            pod.status.phase == "Running"
            and pod.status.container_statuses[container_idx].ready
            and pod.status.container_statuses[container_idx].started
            and pod.status.container_statuses[container_idx].state.running
            and pod.status.container_statuses[container_idx].state.running.started_at
        )

    @property
    def _duplicated_pods_ready(self):
        return all(
            self.pod_ready_and_healthy(pod, self.container)
            for pod in self._gefyra_pods.items
        )

    def prepared(self):
        return self._duplicated_pods_ready

    def ready(self):
        return self._duplicated_pods_ready and self._carrier_installed

    def validate(self, brige_request):
        return super().validate(brige_request)

    def uninstall_service(self) -> None:
        gefyra_svc_name = self._get_duplication_svc_name()
        core_v1_api.delete_namespaced_service(gefyra_svc_name, self.namespace)

    def uninstall_deployment(self) -> None:
        gefyra_deployment_name = self._gefyra_workload_name
        app.delete_namespaced_deployment(gefyra_deployment_name, self.namespace)

    def uninstall(self):
        self.uninstall_deployment()
        self.uninstall_service()
