from copy import deepcopy
from typing import Optional

import kubernetes as k8s
from kubernetes.client import (
    ApiException,
    V2HorizontalPodAutoscaler,
)

from gefyra.bridge_mount.utils import generate_duplicate_hpa_name


DUPLICATION_ID_LABEL = "bridge.gefyra.dev/duplication-id"

ANNOTATION_FILTER = (
    "kubectl.kubernetes.io/last-applied-configuration",
    "deployment.kubernetes.io/revision",
)


def _autoscaling_api() -> "k8s.client.AutoscalingV2Api":
    return k8s.client.AutoscalingV2Api()


def _scale_target_kind_matches(ref_kind: str, target_kind: str) -> bool:
    if not ref_kind:
        return False
    return ref_kind.lower() == target_kind.lower()


def find_hpa_for_target(
    namespace: str,
    target_kind: str,
    target_name: str,
    logger,
) -> Optional[V2HorizontalPodAutoscaler]:
    """Return the first HPA in `namespace` that targets `target_kind/target_name`.

    Multiple matches are a misconfiguration on the cluster — log a warning and
    return the first one. Any API error (e.g. RBAC) degrades to None so that
    HPA support is best-effort and does not block mount creation.
    """
    try:
        hpas = _autoscaling_api().list_namespaced_horizontal_pod_autoscaler(
            namespace=namespace
        )
    except ApiException as e:
        logger.warning(
            f"Cannot list HPAs in namespace '{namespace}' "
            f"(status {e.status}): {e.reason}. Skipping HPA duplication."
        )
        return None

    matches = []
    for hpa in hpas.items:
        ref = hpa.spec.scale_target_ref if hpa.spec else None
        if (
            ref
            and _scale_target_kind_matches(ref.kind, target_kind)
            and ref.name == target_name
        ):
            matches.append(hpa)

    if not matches:
        return None
    if len(matches) > 1:
        names = ", ".join(m.metadata.name for m in matches)
        logger.warning(
            f"Multiple HPAs target {target_kind}/{target_name} in namespace "
            f"'{namespace}' ({names}). Duplicating only the first one."
        )
    return matches[0]


def clone_hpa_for_shadow(
    original_hpa: V2HorizontalPodAutoscaler,
    shadow_workload_name: str,
    duplication_labels: dict,
) -> V2HorizontalPodAutoscaler:
    """Clone an HPA so that the duplicate targets the shadow workload."""
    new_hpa = deepcopy(original_hpa)

    new_hpa.metadata.name = generate_duplicate_hpa_name(original_hpa.metadata.name)
    new_hpa.metadata.resource_version = None
    new_hpa.metadata.uid = None
    new_hpa.metadata.creation_timestamp = None
    new_hpa.metadata.managed_fields = None
    new_hpa.metadata.generation = None
    new_hpa.metadata.owner_references = None
    new_hpa.metadata.self_link = None

    annotations = new_hpa.metadata.annotations or {}
    new_hpa.metadata.annotations = {
        k: v
        for k, v in annotations.items()
        if k not in ANNOTATION_FILTER
        and not k.startswith("autoscaling.alpha.kubernetes.io/")
    } or None

    new_hpa.metadata.labels = dict(duplication_labels)

    new_hpa.spec.scale_target_ref.name = shadow_workload_name

    new_hpa.status = None
    return new_hpa


def read_duplicated_hpa(
    namespace: str, name: str
) -> Optional[V2HorizontalPodAutoscaler]:
    """Return the duplicated HPA if present, None on 404. Other errors bubble
    up so the caller can decide how to handle them."""
    try:
        return _autoscaling_api().read_namespaced_horizontal_pod_autoscaler(
            name=name, namespace=namespace
        )
    except ApiException as e:
        if e.status == 404:
            return None
        raise


def apply_cloned_hpa(namespace: str, cloned_hpa: V2HorizontalPodAutoscaler) -> None:
    api = _autoscaling_api()
    try:
        api.create_namespaced_horizontal_pod_autoscaler(
            namespace=namespace, body=cloned_hpa
        )
    except ApiException as e:
        if e.status == 409:
            api.patch_namespaced_horizontal_pod_autoscaler(
                name=cloned_hpa.metadata.name,
                namespace=namespace,
                body=cloned_hpa,
            )
        else:
            raise


def delete_duplicated_hpa(
    namespace: str,
    original_hpa_name: Optional[str],
    duplication_id: Optional[str],
    logger,
) -> None:
    """Delete the duplicated HPA. Tries direct delete first (if the name is
    derivable), then falls back to label-selector cleanup so dangling clones
    are removed even when the original HPA has disappeared in the meantime."""
    api = _autoscaling_api()

    if original_hpa_name:
        name = generate_duplicate_hpa_name(original_hpa_name)
        try:
            api.delete_namespaced_horizontal_pod_autoscaler(
                name=name, namespace=namespace
            )
        except ApiException as e:
            if e.status != 404:
                logger.warning(
                    f"Failed to delete duplicated HPA '{name}' in "
                    f"namespace '{namespace}': {e.reason} (status {e.status})"
                )

    if not duplication_id:
        return

    try:
        leftovers = api.list_namespaced_horizontal_pod_autoscaler(
            namespace=namespace,
            label_selector=f"{DUPLICATION_ID_LABEL}={duplication_id}",
        )
    except ApiException as e:
        logger.warning(
            f"Failed to list duplicated HPAs by label in namespace "
            f"'{namespace}': {e.reason} (status {e.status})"
        )
        return

    for hpa in leftovers.items:
        try:
            api.delete_namespaced_horizontal_pod_autoscaler(
                name=hpa.metadata.name, namespace=namespace
            )
        except ApiException as e:
            if e.status != 404:
                logger.warning(
                    f"Failed to delete duplicated HPA '{hpa.metadata.name}' "
                    f"in namespace '{namespace}': {e.reason} (status {e.status})"
                )
