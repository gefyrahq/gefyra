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
import asyncio  # Added asyncio import

from gefyra.bridge_mount.abstract import AbstractGefyraBridgeMountProvider
from gefyra.bridge_mount.carrier2mount.hpa import (
    DUPLICATION_ID_LABEL,
    apply_cloned_hpa,
    clone_hpa_for_shadow,
    delete_duplicated_hpa,
    find_hpa_for_target,
    read_duplicated_hpa,
)
from gefyra.bridge_mount.carrier2mount.source_hash import (
    SOURCE_HPA_HASH_ANNOTATION,
    SOURCE_WORKLOAD_HASH_ANNOTATION,
    hash_hpa_source,
    hash_workload_source,
)
from gefyra.configuration import OperatorConfiguration

from gefyra.bridge.carrier2.config import Carrier2Config, Carrier2Proxy, CarrierProbe
from gefyra.bridge_mount.utils import (
    _get_tls_from_provider_parameters,
    generate_duplicate_hpa_name,
    generate_duplicate_workload_name,
    generate_duplicate_svc_name,
    generate_k8s_conform_name,
    get_all_probes,
    get_ports_for_workload,
    get_upstreams_for_svc,
)
from gefyra.utils import async_all, wait_until_condition
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
        self.params = kwargs.get("parameter", {})
        self._duplication_id: str | None = None
        self._original_hpa_name: str | None = None

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
        type_name = type_.__name__ if hasattr(type_, "__name__") else str(type_)
        func = {
            "V1Deployment": app.read_namespaced_deployment,
            "V1StatefulSet": app.read_namespaced_stateful_set,
            "V1Pod": core_v1_api.read_namespaced_pod,
        }.get(type_name)
        if not func:
            raise BridgeMountTargetException(
                f"Cannot select correct Kubernetes API read-op for type '{type_}'"
            )
        return func

    def _create_namespaced_(self, type_) -> Callable:
        type_name = type_.__name__ if hasattr(type_, "__name__") else str(type_)
        func = {
            "V1Deployment": app.create_namespaced_deployment,
            "V1StatefulSet": app.create_namespaced_stateful_set,
            "V1Pod": core_v1_api.create_namespaced_pod,
        }.get(type_name)
        if not func:
            raise BridgeMountInstallException(
                f"Cannot select correct Kubernetes API create-op for type '{type_}'"
            )
        return func

    def _patch_namespaced_(self, type_) -> Callable:
        type_name = type_.__name__ if hasattr(type_, "__name__") else str(type_)
        func = {
            "V1Deployment": app.patch_namespaced_deployment,
            "V1StatefulSet": app.patch_namespaced_stateful_set,
            "V1Pod": core_v1_api.patch_namespaced_pod,
        }.get(type_name)
        if not func:
            raise BridgeMountInstallException(
                f"Cannot select correct Kubernetes API patch-op for type '{type_}'"
            )
        return func

    def _delete_namespaced_(self, type_) -> Callable:
        type_name = type_.__name__ if hasattr(type_, "__name__") else str(type_)
        func = {
            "V1Deployment": app.delete_namespaced_deployment,
            "V1StatefulSet": app.delete_namespaced_stateful_set,
            "V1Pod": core_v1_api.delete_namespaced_pod,
        }.get(type_name)
        if not func:
            raise BridgeMountInstallException(
                f"Cannot select correct Kubernetes API delete-op for type '{type_}'"
            )
        return func

    def _split_target_type_name(
        self, target
    ) -> Tuple[str, Union["V1Deployment", "V1StatefulSet", "V1Pod"]]:
        parts = target.split("/", 1)
        if len(parts) == 2:
            kind, name = parts[0].lower(), parts[1]
        else:
            raise BridgeMountTargetException(
                f"Target format is not correctly specified: {target}"
            )

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
        self,
        workload: V1Deployment | V1StatefulSet | V1Pod,
        duplication_id: str | None = None,
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

        # Reuse an existing duplication-id when re-reconciling an existing
        # shadow, so the service selector (pinned to that id) keeps matching
        # pods across re-applies.
        duplication_id = duplication_id or str(uuid.uuid4())
        self._duplication_id = duplication_id
        if isinstance(workload, (V1Deployment, V1StatefulSet)):
            pod_labels = self._get_duplication_labels(
                new_workload.spec.template.metadata.labels or {}
            )
            # we use this for svc selector
            pod_labels[DUPLICATION_ID_LABEL] = duplication_id
            new_workload.spec.template.metadata.labels = pod_labels

            match_labels = self._get_duplication_labels(
                new_workload.spec.selector.match_labels or {}
            )
            new_workload.spec.selector.match_labels = match_labels
        else:
            # we use this for svc selector
            labels[DUPLICATION_ID_LABEL] = duplication_id
            new_workload.metadata.labels = labels

        new_workload.metadata.annotations = self._clean_annotations(
            new_workload.metadata.annotations or {}
        )
        return new_workload

    @staticmethod
    def _extract_duplication_id(
        shadow: V1Deployment | V1StatefulSet | V1Pod,
    ) -> str | None:
        if isinstance(shadow, (V1Deployment, V1StatefulSet)):
            template = shadow.spec.template if shadow.spec else None
            meta = template.metadata if template else None
            labels = (meta.labels if meta else None) or {}
        else:
            labels = (shadow.metadata.labels if shadow.metadata else None) or {}
        return labels.get(DUPLICATION_ID_LABEL)

    def _get_svc_for_workload(
        self, workload: V1Deployment | V1StatefulSet | V1Pod
    ) -> V1Service:
        name, _ = self._split_target_type_name(self.target)
        if isinstance(workload, (V1Deployment, V1StatefulSet)):
            selector_ = {
                DUPLICATION_ID_LABEL: workload.spec.template.metadata.labels[
                    DUPLICATION_ID_LABEL
                ]
            }
        else:
            selector_ = {
                DUPLICATION_ID_LABEL: workload.metadata.labels[DUPLICATION_ID_LABEL]
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

    async def _read_existing_shadow(
        self,
    ) -> V1Deployment | V1StatefulSet | V1Pod | None:
        """Return the currently deployed shadow workload, or None if it does
        not exist yet. Any other API error bubbles up."""
        _, type_ = self._split_target_type_name(self.target)
        try:
            return await asyncio.to_thread(
                self._read_namespaced_(type_),
                self._gefyra_workload_name,
                self.namespace,
            )
        except ApiException as e:
            if e.status == 404:
                return None
            raise

    async def _duplicate_workload(self) -> None:
        workload = await self._get_workload(self.target, self.namespace)
        source_hash = hash_workload_source(workload)

        existing_shadow = await self._read_existing_shadow()
        if existing_shadow is not None:
            # Remember the existing duplication-id up front, so downstream
            # cleanup paths (HPA, service) can always resolve it even if we
            # take the skip branch below.
            existing_duplication_id = self._extract_duplication_id(existing_shadow)
            if existing_duplication_id:
                self._duplication_id = existing_duplication_id

            existing_annotations = existing_shadow.metadata.annotations or {}
            if existing_annotations.get(SOURCE_WORKLOAD_HASH_ANNOTATION) == source_hash:
                self.logger.info(
                    f"Source workload '{workload.metadata.name}' unchanged "
                    f"(hash {source_hash[:12]}); keeping shadow "
                    f"'{self._gefyra_workload_name}' in place."
                )
                # HPA may still need syncing (its own hash check is idempotent).
                await self._duplicate_hpa_if_present()
                return

        # Build the shadow spec. Reuse the existing duplication-id (if any)
        # so the service selector continues to match running pods.
        new_workload = self._clone_workload_structure(
            workload, duplication_id=self._duplication_id
        )
        new_workload.metadata.annotations = {
            **(new_workload.metadata.annotations or {}),
            SOURCE_WORKLOAD_HASH_ANNOTATION: source_hash,
        }
        new_svc = self._get_svc_for_workload(new_workload)

        if existing_shadow is None:
            try:
                await asyncio.to_thread(
                    self._create_namespaced_(workload.__class__),
                    self.namespace,
                    new_workload,
                )
                await self.post_event(
                    "Cluster upstream",
                    f"Created cluster upstream '{new_workload.metadata.name}' "
                    f"for target workload '{workload.metadata.name}' in namespace '{self.namespace}'.",
                    "Normal",
                )
            except ApiException as e:
                if e.status == 409:
                    # Lost a race: another reconciliation created the shadow.
                    # Fall through to the patch path on the next tick.
                    self.logger.info(
                        f"Shadow workload '{new_workload.metadata.name}' was "
                        f"created concurrently; will reconcile next tick."
                    )
                    return
                raise BridgeInstallException(f"Exception when creating workload: {e}")
        else:
            # Patch path: the shadow's replica count is owned by the
            # duplicated HPA (see GO-1030); do not reset it here.
            if hasattr(new_workload.spec, "replicas"):
                new_workload.spec.replicas = None
            await asyncio.to_thread(
                self._patch_namespaced_(workload.__class__),
                name=new_workload.metadata.name,
                namespace=self.namespace,
                body=new_workload,
            )
            await self.post_event(
                "Cluster upstream",
                f"Re-applied cluster upstream '{new_workload.metadata.name}' "
                f"after source workload change (hash {source_hash[:12]}).",
                "Normal",
            )

        try:
            await asyncio.to_thread(
                core_v1_api.create_namespaced_service,
                self.namespace,
                new_svc,
            )
            await self.post_event(
                "Cluster upstream service",
                f"Created cluster upstream service '{new_svc.metadata.name}' "
                f"in namespace '{self.namespace}'.",
                "Normal",
            )
        except ApiException as e:
            if e.status == 409:
                await asyncio.to_thread(
                    core_v1_api.patch_namespaced_service,
                    name=new_svc.metadata.name,
                    namespace=self.namespace,
                    body=new_svc,
                )
            else:
                raise BridgeInstallException(f"Exception when creating service: {e}")

        await self._duplicate_hpa_if_present()

    def _hpa_target_kind(self) -> str | None:
        _, type_ = self._split_target_type_name(self.target)
        if type_ is V1Deployment:
            return "Deployment"
        if type_ is V1StatefulSet:
            return "StatefulSet"
        return None

    async def _read_existing_shadow_hpa(self, name: str):
        return await asyncio.to_thread(
            read_duplicated_hpa, self.namespace, name
        )

    async def _duplicate_hpa_if_present(self) -> None:
        """Discover an HPA on the original workload and duplicate it onto the
        shadow workload. Optional feature: failures are logged but never raise,
        so HPA-less workloads and clusters without RBAC for autoscaling/v2
        keep working as before.

        Idempotent: if the duplicated HPA already exists and its source-hash
        annotation matches the original, the call is a no-op — no write to the
        apiserver, no perturbation of shadow scaling decisions."""
        target_kind = self._hpa_target_kind()
        if target_kind is None:
            # Pods aren't HPA targets.
            return
        target_name, _ = self._split_target_type_name(self.target)
        try:
            original_hpa = await asyncio.to_thread(
                find_hpa_for_target,
                self.namespace,
                target_kind,
                target_name,
                self.logger,
            )
            if original_hpa is None:
                self.logger.info(
                    f"No HPA found for {target_kind}/{target_name} in "
                    f"namespace '{self.namespace}'. Skipping HPA duplication."
                )
                return

            self._original_hpa_name = original_hpa.metadata.name
            source_hash = hash_hpa_source(original_hpa)

            duplicated_name = generate_duplicate_hpa_name(
                original_hpa.metadata.name
            )
            existing = await self._read_existing_shadow_hpa(duplicated_name)
            if existing is not None:
                existing_hash = (existing.metadata.annotations or {}).get(
                    SOURCE_HPA_HASH_ANNOTATION
                )
                if existing_hash == source_hash:
                    self.logger.info(
                        f"HPA '{original_hpa.metadata.name}' unchanged "
                        f"(hash {source_hash[:12]}); keeping duplicated "
                        f"HPA '{duplicated_name}' in place."
                    )
                    return

            duplication_labels = self._get_duplication_labels(
                original_hpa.metadata.labels or {}
            )
            if self._duplication_id:
                duplication_labels[DUPLICATION_ID_LABEL] = self._duplication_id

            cloned = clone_hpa_for_shadow(
                original_hpa=original_hpa,
                shadow_workload_name=self._gefyra_workload_name,
                duplication_labels=duplication_labels,
            )
            cloned.metadata.annotations = {
                **(cloned.metadata.annotations or {}),
                SOURCE_HPA_HASH_ANNOTATION: source_hash,
            }
            await asyncio.to_thread(apply_cloned_hpa, self.namespace, cloned)
            verb = "Updated" if existing is not None else "Duplicated"
            await self.post_event(
                "Cluster upstream HPA",
                f"{verb} HPA '{original_hpa.metadata.name}' as "
                f"'{cloned.metadata.name}' targeting shadow workload "
                f"'{self._gefyra_workload_name}' in namespace "
                f"'{self.namespace}'.",
                "Normal",
            )
        except Exception as e:
            self.logger.warning(
                f"Failed to duplicate HPA for {target_kind}/{target_name} "
                f"in namespace '{self.namespace}': {e}. The shadow workload "
                f"will not auto-scale."
            )
            await self.post_event(
                "Cluster upstream HPA",
                f"Failed to duplicate HPA for {target_kind}/{target_name}: {e}",
                "Warning",
            )

    async def _resolve_duplication_id(self) -> str | None:
        if self._duplication_id:
            return self._duplication_id
        try:
            shadow = await self._read_existing_shadow()
        except ApiException:
            return None
        if shadow is None:
            return None
        duplication_id = self._extract_duplication_id(shadow)
        if duplication_id:
            self._duplication_id = duplication_id
        return duplication_id

    async def _uninstall_duplicated_hpa(self) -> None:
        if self._hpa_target_kind() is None:
            return
        try:
            duplication_id = await self._resolve_duplication_id()
            await asyncio.to_thread(
                delete_duplicated_hpa,
                self.namespace,
                self._original_hpa_name,
                duplication_id,
                self.logger,
            )
        except Exception as e:
            # A dangling HPA can be cleaned up manually; never block restore.
            self.logger.error(
                f"Failed to clean up duplicated HPA for {self.name} "
                f"in namespace '{self.namespace}': {e}"
            )

    async def _get_workload(
        self, target: str, namespace: str
    ) -> V1Deployment | V1StatefulSet | V1Pod:
        name, type_ = self._split_target_type_name(target)
        try:
            result = await asyncio.to_thread(
                self._read_namespaced_(type_), name, namespace
            )
        except ApiException as e:
            if e.status == 404:
                raise BridgeMountTargetException(
                    f"Workload target {target} (type '{type_.__name__}') in namespace '{namespace}' not found."
                )
            raise RuntimeError(f"Exception when calling Kubernetes API: {e}") from e
        return result

    async def prepare(self):
        try:
            await self._duplicate_workload()
        except Exception as e:
            raise BridgeMountInstallException(e)

    @property
    async def _gefyra_pods(self) -> V1PodList:
        _, type_ = self._split_target_type_name(self.target)
        return await self.get_pods_workload(
            name=f"{self._gefyra_workload_type}/{self._gefyra_workload_name}",
            namespace=self.namespace,
        )

    @property
    async def _original_pods(self) -> V1PodList:
        return await self.get_pods_workload(
            name=self.target,
            namespace=self.namespace,
        )

    async def get_pods_workload(self, name: str, namespace: str) -> V1PodList:
        API_EXCEPTION_MSG = "Exception when calling Kubernetes API: {}"
        NOT_FOUND_MSG = f"Target {name} not found in namespace '{namespace}'."
        try:
            workload = await self._get_workload(name, namespace)
        except ApiException as e:
            if e.status == 404:
                raise BridgeMountTargetException(NOT_FOUND_MSG)
            raise RuntimeError(API_EXCEPTION_MSG.format(e)) from e

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
        pods = await asyncio.to_thread(
            core_v1_api.list_namespaced_pod,
            namespace=namespace,
            label_selector=label_selector,
        )
        return pods

    async def _default_upstream(self, rport: int) -> List[str]:
        if hasattr(self, "_default_upstream_cache") and self._default_upstream_cache:
            return self._default_upstream_cache
        name, _ = self._split_target_type_name(self.target)
        svc_name = generate_duplicate_svc_name(
            workload_name=name, container_name=self.container
        )
        svc = await asyncio.to_thread(
            core_v1_api.read_namespaced_service, svc_name, self.namespace
        )
        self._default_upstream_cache = get_upstreams_for_svc(svc=svc, rport=rport)
        return self._default_upstream_cache

    async def _set_carrier_upstream(
        self, upstream_ports: list[int], probes: List[V1Probe]
    ) -> Carrier2Config:
        carrier_config = Carrier2Config()

        for upstream_port in upstream_ports:
            carrier_config.proxy.append(
                Carrier2Proxy(
                    port=upstream_port,
                    clusterUpstream=await self._default_upstream(upstream_port),
                    tls=_get_tls_from_provider_parameters(self.params),
                )
            )

        if probes:
            carrier_config.probes = CarrierProbe(
                httpGet=list(
                    set(
                        probe.http_get.port
                        for probe in probes
                        if probe.http_get.port not in upstream_ports
                        and (
                            not probe.http_get.scheme
                            or probe.http_get.scheme.lower() == "http"
                        )
                    )
                ),
                httpsGet=list(
                    set(
                        probe.http_get.port
                        for probe in probes
                        if probe.http_get.port not in upstream_ports
                        and (
                            probe.http_get.scheme
                            and probe.http_get.scheme.lower() == "https"
                        )
                    )
                ),
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

    async def install(self):
        upstream_ports = []
        pods = await self._original_pods
        if (
            len(
                set(
                    pod.metadata.owner_references[0].name
                    for pod in pods.items
                    if pod.metadata.owner_references
                )
            )
            > 1
        ):
            # there is probably an update in progress
            raise TemporaryError(
                "Cannot install Gefyra Carrier2 on pods controlled by more than one controller.",
                delay=10,
            )
        for idx, pod in enumerate(pods.items):
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
                        # Returning False, pod is not possible in async, either raise or return None and handle it
                        raise BridgeInstallException("Probes not compatible")
                    if container.image == self._carrier_image:
                        # this pod/container is already running Carrier
                        self.logger.info(
                            f"The container {self.container} in Pod {pod.metadata.name} is already"
                            " running Carrier2"
                        )
                    await self._store_pod_original_config(container, pod.metadata.name)
                    container.image = self._carrier_image
                    break
            else:
                raise BridgeInstallException(
                    f"Container {self.container} not found in Pod {pod}"
                )
            await self.post_event(
                "Patching target pod",
                f"Now patching Pod {pod.metadata.name} ({idx + 1} of {len(pods.items)} Pod(s)); container {self.container} with Carrier2",
                "Normal",
            )
            try:
                await asyncio.to_thread(
                    core_v1_api.patch_namespaced_pod,
                    name=pod.metadata.name,
                    namespace=self.namespace,
                    body=pod,
                )
            except ApiException as e:
                self.logger.warning(
                    f"Failed to patch Pod {pod.metadata.name} with Carrier2: {e.reason} (status {e.status})"
                )
                raise TemporaryError(
                    f"Failed to patch Pod {pod.metadata.name} with Carrier2: {e.reason} (status {e.status})",
                    delay=10,
                )

            # wait for the container restart to become effective
            read_func = partial(
                core_v1_api.read_namespaced_pod_status,
                pod.metadata.name,
                self.namespace,
            )
            await asyncio.to_thread(
                wait_until_condition,
                read_func,
                lambda s: (
                    next(
                        filter(
                            lambda c: c.name == self.container,
                            s.status.container_statuses,
                        )
                    ).restart_count
                    > 0
                ),
                timeout=120,
                backoff=0.2,
            )

            carrier_config = await self._set_carrier_upstream(upstream_ports, probes)
            await carrier_config.add_bridge_rules_for_mount(
                self.name, self.configuration.NAMESPACE, None, None
            )
            # await self.post_event(
            #     "Update Carrier2",
            #     f"Commiting Carrier2 config to Pod {pod.metadata.name} ({idx + 1} of {len(pods.items)} Pod(s))",
            #     "Normal",
            # )
            self.logger.debug(f"Carrier2 config: {carrier_config}")
            try:
                await carrier_config.commit(
                    self.logger,
                    pod.metadata.name,
                    self.container,
                    self.namespace,
                    debug=self.configuration.CARRIER2_DEBUG,
                )
            except RuntimeError:
                raise BridgeInstallException(
                    f"Could not install GefyraBridgeMount successfully. Please check the log of the patched Pod '{pod.metadata.name}'"
                    f" and container '{self.container}' in namespace '{self.namespace}' for more information."
                )

    @property
    async def _carrier_installed(self):
        res = True
        pods = await self._original_pods  # Await the async property
        for pod in pods.items:
            for container in pod.spec.containers:
                if container.name == self.container:
                    res = res and container.image == self._carrier_image
        return res

    def _pod_is_running(self, pod: V1Pod) -> bool:
        return pod.status.phase == "Running"

    # TODO this util exists in the client aswell and Carrier2
    # maybe refactor
    async def pod_ready_and_healthy(self, pod: V1Pod, container_name: str) -> bool:
        if not pod.status.container_statuses:
            return False
        container_idx = next(
            i
            for i, container_status in enumerate(pod.status.container_statuses)
            if container_status.name == container_name
        )
        return bool(
            self._pod_is_running(pod)
            and pod.status.container_statuses[container_idx].ready
            and pod.status.container_statuses[container_idx].started
            and pod.status.container_statuses[container_idx].state.running
            and pod.status.container_statuses[container_idx].state.running.started_at
        )

    @property
    async def _original_pods_ready(self):
        pods = await self._original_pods  # Await the async property
        return await async_all(
            await self.pod_ready_and_healthy(pod, self.container) for pod in pods.items
        )

    @property
    async def _duplicated_pods_ready(self):
        pods = await self._gefyra_pods
        return await async_all(
            await self.pod_ready_and_healthy(pod, self.container) for pod in pods.items
        )

    @property
    async def _upstream_set(self) -> bool:
        pods = await self._original_pods  # Await the async property
        if not pods.items:
            self.logger.error("Cannot determine original pods")
            return False
        for pod in pods.items:
            config_str_list = await asyncio.to_thread(
                read_carrier2_config,
                self.logger,
                pod.metadata.name,
                self.namespace,
            )
            config_str = "\n".join(config_str_list)
            pod_config = Carrier2Config.from_string(config_str)
            if not any(p.clusterUpstream for p in pod_config.proxy):
                return False
        return True

    async def restore_original_workload(
        self,
    ) -> Union["V1Deployment", "V1StatefulSet", "V1Pod"]:
        _, type_ = self._split_target_type_name(self.target)
        workload = await self._get_workload(self.target, self.namespace)
        if hasattr(workload.spec, "template") and workload.spec.template is not None:
            workload.spec.template.metadata.annotations = {
                "kubectl.kubernetes.io/restartedAt": datetime.datetime.now().isoformat()
            }
            new_workload = await asyncio.to_thread(
                self._patch_namespaced_(type_),
                name=workload.metadata.name,
                namespace=self.namespace,
                body=workload,
            )
        else:
            new_workload = await self._patch_pod_with_original_config(
                workload.metadata.name
            )
        return new_workload

    async def prepared(self):
        pods_ready = await self._duplicated_pods_ready
        if not pods_ready:
            self.logger.info(
                "Not all duplicated pods are ready yet for the GefyraBridgeMount."
            )
        return pods_ready

    async def ready(self):
        ready = (
            await self._duplicated_pods_ready
            and await self._carrier_installed
            and await self._original_pods_ready
            and await self._upstream_set
        )
        if not ready:
            self.logger.info(
                "GefyraBridgeMount is not ready yet: "
                f"duplicated pods ready: {await self._duplicated_pods_ready}, "
                f"carrier installed: {await self._carrier_installed}, "
                f"original pods ready: {await self._original_pods_ready}, "
                f"upstream set: {await self._upstream_set}"
            )
        return ready

    async def validate(self, bridge_request, hints):
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

            bridge_mounts = await asyncio.to_thread(
                custom_object_api.list_namespaced_custom_object,
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

    async def uninstall_service(self) -> None:
        gefyra_svc_name = self.gefyra_svc_name()
        try:
            await asyncio.to_thread(
                core_v1_api.delete_namespaced_service, gefyra_svc_name, self.namespace
            )
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

    async def uninstall_duplicated_workload(self) -> None:
        _, type_ = self._split_target_type_name(self.target)
        gefyra_deployment_name = self._gefyra_workload_name
        try:
            await asyncio.to_thread(
                self._delete_namespaced_(type_), gefyra_deployment_name, self.namespace
            )
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

    async def _store_pod_original_config(
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
            await asyncio.to_thread(
                core_v1_api.patch_namespaced_config_map,
                name=CARRIER2_ORIGINAL_CONFIGMAP,
                namespace=self.configuration.NAMESPACE,
                body=config,
            )
        except k8s.client.exceptions.ApiException as e:
            if e.status == 404:
                await asyncio.to_thread(
                    core_v1_api.create_namespaced_config_map,
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

    async def _patch_pod_with_original_config(self, pod_name: str) -> V1Pod:
        pod = await asyncio.to_thread(
            core_v1_api.read_namespaced_pod, name=pod_name, namespace=self.namespace
        )
        configmap = await asyncio.to_thread(
            core_v1_api.read_namespaced_config_map,
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
                f"Could not find container {self.container} in Pod {pod_name}: cannot"
                " patch with original state"
            )

        self.logger.info(
            f"Now patching Pod {pod_name}; container {self.container} with original"
            " state"
        )
        return await asyncio.to_thread(
            core_v1_api.patch_namespaced_pod,
            name=pod_name,
            namespace=self.namespace,
            body=pod,
        )

    async def target_exists(self) -> bool:
        try:
            await asyncio.to_thread(core_v1_api.read_namespace, self.namespace)
        except ApiException as e:
            if e.status == 404:
                return False
            raise
        try:
            await self._get_workload(self.target, self.namespace)
        except BridgeMountTargetException:
            return False
        return True

    async def uninstall(self):
        await self.uninstall_duplicated_workload()
        await self.uninstall_service()
        await self._uninstall_duplicated_hpa()
        try:
            await self.restore_original_workload()
        except Exception as e:
            self.logger.error(
                f"Could not restore original workload for {self.name} due to: {e}"
            )
