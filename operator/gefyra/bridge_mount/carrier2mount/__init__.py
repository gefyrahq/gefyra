from copy import deepcopy
import datetime
from functools import partial
import json
from typing import Callable, List, Tuple, Union
import uuid
from kopf import TemporaryError
import kopf
import kubernetes as k8s
from kubernetes.client import (
    V1Deployment,
    V1StatefulSet,
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

from gefyra.bridge.carrier2.config import Carrier2Config, Carrier2Proxy, CarrierProbe
from gefyra.bridge_mount.utils import (
    _get_tls_from_provider_parameters,
    generate_duplicate_workload_name,
    generate_duplicate_svc_name,
    generate_k8s_conform_name,
    get_all_probes,
    get_ports_for_workload,
    get_upstreams_for_svc,
)
from gefyra.utils import wait_until_condition
from gefyra.bridge.carrier2.utils import read_carrier2_config
from gefyra.bridge.exceptions import BridgeInstallException
from gefyra.bridge_mount.exceptions import (
    BridgeMountException,
    BridgeMountInstallException,
    BridgeMountTargetException,
)

app = k8s.client.AppsV1Api()
core_v1_api = k8s.client.CoreV1Api()
custom_object_api = k8s.client.CustomObjectsApi()

CARRIER2_ORIGINAL_CONFIGMAP = "gefyra-carrier2-restore-configmap"


class Carrier2BridgeMount(AbstractGefyraBridgeMountProvider):
    provider_type = "carrier2mount"

    def __init__(
        self,
        configuration: OperatorConfiguration,
        name: str,
        target_namespace: str,
        target: str,
        target_container: str,
        post_event_function: Callable[[str, str, str], None],
        logger,
        **kwargs,
    ) -> None:
        self.configuration = configuration
        self.namespace = target_namespace
        self.target = target
        self.container = target_container
        self.name = name
        self.post_event = post_event_function
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
        name, _ = self._split_target_type_name(self.target)
        return f"{name}-gefyra"

    @property
    def _gefyra_workload_type(self) -> str:
        _, type_ = self._split_target_type_name(self.target)
        if type_ is V1Deployment:
            return "deployment"
        elif type_ is V1StatefulSet:
            return "statefulset"
        else:
            return "pod"

    def _read_namespaced_(self, type_) -> Callable:
        func = {
            V1Deployment: app.read_namespaced_deployment,
            V1StatefulSet: app.read_namespaced_stateful_set,
            V1Pod: core_v1_api.read_namespaced_pod,
        }.get(type_)
        if not func:
            raise BridgeMountTargetException(
                f"Cannont select correct Kubernetes API read-op for type '{type_}'"
            )
        return func

    def _create_namespaced_(self, type_) -> Callable:
        func = {
            V1Deployment: app.create_namespaced_deployment,
            V1StatefulSet: app.create_namespaced_stateful_set,
            V1Pod: core_v1_api.create_namespaced_pod,
        }.get(type_)
        if not func:
            raise BridgeMountInstallException(
                f"Cannont select correct Kubernetes API create-op for type '{type_}'"
            )
        return func

    def _patch_namespaced_(self, type_) -> Callable:
        func = {
            V1Deployment: app.patch_namespaced_deployment,
            V1StatefulSet: app.patch_namespaced_stateful_set,
            V1Pod: core_v1_api.patch_namespaced_pod,
        }.get(type_)
        if not func:
            raise BridgeMountInstallException(
                f"Cannont select correct Kubernetes API patch-op for type '{type_}'"
            )
        return func

    def _delete_namespaced_(self, type_) -> Callable:
        func = {
            V1Deployment: app.delete_namespaced_deployment,
            V1StatefulSet: app.delete_namespaced_stateful_set,
            V1Pod: core_v1_api.delete_namespaced_pod,
        }.get(type_)
        if not func:
            raise BridgeMountInstallException(
                f"Cannont select correct Kubernetes API delete-op for type '{type_}'"
            )
        return func

    def _split_target_type_name(
        self, target
    ) -> Tuple[str, Union["V1Deployment", "V1StatefulSet", "V1Pod"]]:
        parts = target.split("/", 1)
        if len(parts) == 2:
            kind, name = parts[0].lower(), parts[1]
        else:
            # assume it's a pod name if no kind prefix is provided
            kind, name = "pod", parts[0]

        if kind in ("deployment", "deploy", "deployments"):
            type_ = V1Deployment
        elif kind in ("statefulset", "sts", "statefulsets"):
            type_ = V1StatefulSet
        elif kind in ("pod", "po", "pods"):
            type_ = V1Pod
        else:
            raise BridgeMountException(
                f"Unsupported workload kind '{kind}' in reference {target}"
            )
        return name, type_

    def _clone_workload_structure(
        self, workload: V1Deployment | V1StatefulSet | V1Pod
    ) -> V1Deployment | V1StatefulSet | V1Pod:
        new_workload = deepcopy(workload)

        # Update labels to add -gefyra suffix
        labels = self._get_duplication_labels(new_workload.metadata.labels or {})
        new_workload.metadata.labels = labels
        new_workload.metadata.resource_version = None
        new_workload.metadata.uid = None

        new_workload.metadata.name = generate_duplicate_workload_name(
            workload.metadata.name
        )

        if isinstance(workload, (V1Deployment, V1StatefulSet)):
            pod_labels = self._get_duplication_labels(
                new_workload.spec.template.metadata.labels or {}
            )
            # we use this for svc selector
            pod_labels["bridge.gefyra.dev/duplication-id"] = str(uuid.uuid4())
            new_workload.spec.template.metadata.labels = pod_labels

            match_labels = self._get_duplication_labels(
                new_workload.spec.selector.match_labels or {}
            )
            new_workload.spec.selector.match_labels = match_labels
        else:
            pod_labels = self._get_duplication_labels(
                new_workload.metadata.labels or {}
            )
            # we use this for svc selector
            pod_labels["bridge.gefyra.dev/duplication-id"] = str(uuid.uuid4())
            new_workload.metadata.labels = pod_labels

        new_workload.metadata.annotations = self._clean_annotations(
            new_workload.metadata.annotations or {}
        )
        return new_workload

    def _get_svc_for_workload(
        self, workload: V1Deployment | V1StatefulSet | V1Pod
    ) -> V1Service:
        name, _ = self._split_target_type_name(self.target)
        if isinstance(workload, (V1Deployment, V1StatefulSet)):
            selector_ = {
                "bridge.gefyra.dev/duplication-id": workload.spec.template.metadata.labels[
                    "bridge.gefyra.dev/duplication-id"
                ]
            }
        else:
            selector_ = {
                "bridge.gefyra.dev/duplication-id": workload.metadata.labels[
                    "bridge.gefyra.dev/duplication-id"
                ]
            }
        return V1Service(
            metadata=V1ObjectMeta(
                name=generate_duplicate_svc_name(
                    workload_name=name, container_name=self.container
                ),
                labels=workload.metadata.labels,
            ),
            spec=V1ServiceSpec(
                selector=selector_,
                ports=get_ports_for_workload(
                    workload=workload, container_name=self.container
                ),
            ),
        )

    def _duplicate_workload(self) -> None:
        workload = self._get_workload(self.target, self.namespace)

        # Create a copy of the workload

        new_workload = self._clone_workload_structure(workload)
        new_svc = self._get_svc_for_workload(new_workload)

        # Create the new workload
        try:

            self._create_namespaced_(workload.__class__)(self.namespace, new_workload)
            self.post_event(
                "Cluster upstream",
                f"Created cluster upstream '{new_workload.metadata.name}' "
                f"for target workload '{workload.metadata.name}' in namespace '{self.namespace}'.",
                "Normal",
            )
        except ApiException as e:
            if e.status == 409:
                self._patch_namespaced_(workload.__class__)(
                    name=new_workload.metadata.name,
                    namespace=self.namespace,
                    body=new_workload,
                )
            else:
                raise BridgeInstallException(f"Exception when creating workload: {e}")
        try:
            core_v1_api.create_namespaced_service(
                self.namespace,
                new_svc,
            )
            self.post_event(
                "Cluster upstream service",
                f"Created cluster upstream service '{new_svc.metadata.name}' "
                f"in namespace '{self.namespace}'.",
                "Normal",
            )
        except ApiException as e:
            if e.status == 409:
                core_v1_api.patch_namespaced_service(
                    name=new_svc.metadata.name,
                    namespace=self.namespace,
                    body=new_svc,
                )
            else:
                raise BridgeInstallException(f"Exception when creating service: {e}")

    def _get_workload(
        self, target: str, namespace: str
    ) -> V1Deployment | V1StatefulSet | V1Pod:

        name, type_ = self._split_target_type_name(target)
        try:
            return self._read_namespaced_(type_)(name, namespace)
        except ApiException as e:
            if e.status == 404:
                raise BridgeMountTargetException(
                    f"Workload target {target} (type '{type_.__name__}') in namespace '{namespace}' not found."
                )
            raise RuntimeError(f"Exception when calling Kubernetes API: {e}")

    def prepare(self):
        try:
            self._duplicate_workload()
        except Exception as e:
            raise BridgeMountInstallException(e)

    @property
    def _gefyra_pods(self) -> V1PodList:
        _, type_ = self._split_target_type_name(self.target)
        return self.get_pods_workload(
            name=f"{self._gefyra_workload_type}/{self._gefyra_workload_name}",
            namespace=self.namespace,
        )

    @property
    def _original_pods(self) -> V1PodList:
        return self.get_pods_workload(
            name=self.target,
            namespace=self.namespace,
        )

    def get_pods_workload(self, name: str, namespace: str) -> V1PodList:
        API_EXCEPTION_MSG = "Exception when calling Kubernetes API: {}"
        NOT_FOUND_MSG = f"Target {name} not found in namespace '{namespace}'."
        try:
            workload = self._get_workload(name, namespace)
        except ApiException as e:
            if e.status == 404:
                raise BridgeMountTargetException(NOT_FOUND_MSG)
            raise RuntimeError(API_EXCEPTION_MSG.format(e))

        # use workloads metadata uuid for owner references with field selector to get pods
        if isinstance(workload, (V1Deployment, V1StatefulSet)):
            v1_label_selector = workload.spec.selector.match_labels
        else:
            v1_label_selector = workload.metadata.labels

        label_selector = ",".join(
            [f"{key}={value}" for key, value in v1_label_selector.items()]
        )

        if not label_selector:
            # TODO better exception typing here
            raise Exception(f"No label selector set for {self.target}.")
        pods = core_v1_api.list_namespaced_pod(
            namespace=namespace, label_selector=label_selector
        )
        return pods

    def _default_upstream(self, rport: int) -> List[str]:
        name, _ = self._split_target_type_name(self.target)
        svc_name = generate_duplicate_svc_name(
            workload_name=name, container_name=self.container
        )
        svc = core_v1_api.read_namespaced_service(svc_name, self.namespace)
        return get_upstreams_for_svc(svc=svc, rport=rport)

    def _set_carrier_upstream(
        self, upstream_ports: list[int], probes: List[V1Probe]
    ) -> Carrier2Config:
        carrier_config = Carrier2Config()

        for upstream_port in upstream_ports:
            carrier_config.proxy.append(
                Carrier2Proxy(
                    port=upstream_port,
                    clusterUpstream=self._default_upstream(upstream_port),
                    tls=_get_tls_from_provider_parameters(self.params),
                )
            )

        if probes:
            carrier_config.probes = CarrierProbe(
                httpGet=[probe.http_get.port for probe in probes]
            )
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
        upstream_ports = []
        pods = self._original_pods.items
        if (
            len(
                set(
                    pod.metadata.owner_references[0].name
                    for pod in pods
                    if pod.metadata.owner_references
                )
            )
            > 1
        ):
            # there is probably an update in progress
            raise TemporaryError(
                "Cannot install Gefyra Carrier2 on pods controlled by more than one controller.",
                delay=5,
            )
        for idx, pod in enumerate(pods):
            if pod.status.phase == "Terminating":
                continue
            for container in pod.spec.containers:
                if container.name == self.container:
                    upstream_ports = [port.container_port for port in container.ports]
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
                    self._store_pod_original_config(container, pod.metadata.name)
                    container.image = self._carrier_image
                    break
            else:
                raise BridgeInstallException(
                    f"Container {self.container} not found in Pod {pod}"
                )
            self.post_event(
                "Patching target pod",
                f"Now patching Pod {pod.metadata.name} ({idx+1} of {len(pods)} Pod(s)); container {self.container} with Carrier2",
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
            carrier_config.add_bridge_rules_for_mount(
                self.name, self.configuration.NAMESPACE, None
            )
            self.post_event(
                "Update Carrier2",
                f"Commiting Carrier2 config to Pod {pod.metadata.name} ({idx+1} of {len(pods)} Pod(s))",
            )
            self.logger.debug(f"Carrier2 config: {carrier_config}")
            try:
                carrier_config.commit(
                    pod.metadata.name,
                    self.container,
                    self.namespace,
                    debug=self.configuration.CARRIER2_DEBUG,
                )
            except RuntimeError:
                raise BridgeInstallException(
                    f"Could not install GefyraBridgeMount successfully. Please check the log of the patched Pod '{pod.metadata.name}'"
                    f"and container '{self.container}' in namespace '{self.namespace}' for more information."
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
            if not any(p.clusterUpstream for p in pod_config.proxy):
                return False
            ## TODO check container of pod and port
            return True
        self.logger.error("Cannot determine original pods")
        return False

    def restore_original_workload(
        self,
    ) -> Union["V1Deployment", "V1StatefulSet", "V1Pod"]:
        _, type_ = self._split_target_type_name(self.target)
        workload = self._get_workload(self.target, self.namespace)
        if isinstance(workload, (V1Deployment, V1StatefulSet)):
            workload.spec.template.metadata.annotations = {
                "kubectl.kubernetes.io/restartedAt": datetime.datetime.now().isoformat()
            }
            new_workload = self._patch_namespaced_(type_)(
                name=workload.metadata.name, namespace=self.namespace, body=workload
            )
        else:
            new_workload = self._patch_pod_with_original_config(workload.metadata.name)
        return new_workload

    def prepared(self):
        return self._duplicated_pods_ready

    def ready(self):
        ready = (
            self._duplicated_pods_ready
            and self._carrier_installed
            and self._original_pods_ready
            and self._upstream_set
        )
        # consider down scaling & up scaling
        return ready and len(self._gefyra_pods.items) == len(self._original_pods.items)

    def validate(self, bridge_request, hints):

        required_fields = ["target", "targetNamespace", "targetContainer"]
        for required_field in required_fields:
            if (
                required_field not in bridge_request
                or bridge_request[required_field] == ""
            ):
                raise kopf.AdmissionError(
                    f"The field '{required_field}' must not be empty"
                )

        # we cannot allow more GefyraBridgeMounts for the same workload
        # e.g. deploy/a deployment/a sts/b and others
        try:
            target = bridge_request["target"]
            self._split_target_type_name(target)  # expect RuntimeError if malformed
            target_namespace = bridge_request["targetNamespace"]

            bridge_mounts = custom_object_api.list_namespaced_custom_object(
                group="gefyra.dev",
                version="v1",
                plural="gefyrabridgemounts",
                namespace=self.configuration.NAMESPACE,
            )
        except Exception as e:
            raise kopf.AdmissionError(f"Cannot read GefyraBridgeMounts: {e}")
        for bridge_mount in bridge_mounts.get("items"):
            if (
                bridge_mount["target"] == target
                and bridge_mount["targetNamespace"] == target_namespace
            ):
                raise kopf.AdmissionError(
                    f"A GefyraBridgeMount already exists for target '{target}' in namespace '{target_namespace}':"
                    f"'{bridge_mount['metadata']['name']}' in state '{bridge_mount['state']}'"
                )

    def uninstall_service(self) -> None:
        gefyra_svc_name = self.gefyra_svc_name()
        try:
            core_v1_api.delete_namespaced_service(gefyra_svc_name, self.namespace)
        except ApiException as e:
            if e.status == 404:
                self.logger.warning(
                    f"Service {gefyra_svc_name} not found in namespace {self.namespace}."
                )
            else:
                self.logger.error(
                    f"Exception when deleting service {gefyra_svc_name}: {e}"
                )
                raise e

    def gefyra_svc_name(self):
        name, _ = self._split_target_type_name(self.target)
        gefyra_svc_name = generate_duplicate_svc_name(name, self.container)
        return gefyra_svc_name

    def uninstall_duplicated_workload(self) -> None:
        _, type_ = self._split_target_type_name(self.target)
        gefyra_deployment_name = self._gefyra_workload_name
        try:
            self._delete_namespaced_(type_)(gefyra_deployment_name, self.namespace)
        except ApiException as e:
            if e.status == 404:
                self.logger.warning(
                    f"Workload {type_.__name__}/{gefyra_deployment_name} not found in namespace {self.namespace}."
                )
            else:
                self.logger.error(
                    f"Exception when deleting workload {type_.__name__}/{gefyra_deployment_name}: {e}"
                )
                raise e

    def _store_pod_original_config(
        self, container: k8s.client.V1Container, pod_name: str
    ) -> None:
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
            {"op": "add", "path": f"/data/{self.namespace}-{pod_name}", "value": data}
        ]
        try:
            core_v1_api.patch_namespaced_config_map(
                name=CARRIER2_ORIGINAL_CONFIGMAP,
                namespace=self.configuration.NAMESPACE,
                body=config,
            )
        except k8s.client.exceptions.ApiException as e:
            if e.status == 404:
                core_v1_api.create_namespaced_config_map(
                    namespace=self.configuration.NAMESPACE,
                    body=k8s.client.V1ConfigMap(
                        metadata=k8s.client.V1ObjectMeta(
                            name=CARRIER2_ORIGINAL_CONFIGMAP
                        ),
                        data={
                            f"{self.namespace}-{pod_name}": data,
                        },
                    ),
                )
            else:
                raise e

    def _patch_pod_with_original_config(self, pod_name: str) -> V1Pod:
        pod = core_v1_api.read_namespaced_pod(name=pod_name, namespace=self.namespace)
        configmap = core_v1_api.read_namespaced_config_map(
            name=CARRIER2_ORIGINAL_CONFIGMAP,
            namespace=self.configuration.NAMESPACE,
        )
        data = json.loads(configmap.data.get(f"{self.namespace}-{pod_name}"))

        for container in pod.spec.containers:
            if container.name == self.container:
                for k, v in data.get("originalConfig").items():
                    setattr(container, k, v)
                break
        else:
            raise RuntimeError(
                f"Could not found container {self.container} in Pod {pod_name}: cannot"
                " patch with original state"
            )

        self.logger.info(
            f"Now patching Pod {pod_name}; container {self.container} with original"
            " state"
        )
        return core_v1_api.patch_namespaced_pod(
            name=pod_name, namespace=self.namespace, body=pod
        )

    def uninstall(self):
        self.uninstall_duplicated_workload()
        self.uninstall_service()
        self.restore_original_workload()
