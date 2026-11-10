"""Targeted pod-template updates; never replace StatefulSet storage or selectors."""

import json

from kubernetes.client import ApiClient

from gefyra.connection.stowaway.resources.statefulsets import (
    MANAGED_POD_LABELS_ANNOTATION,
)
from gefyra.stowaway_config import STOWAWAY_LABELS


def _tolerations(items):
    # The API defaults operator to Equal; absent/empty optional strings are equivalent.
    return [
        {
            "key": item.get("key") or "",
            "operator": item.get("operator") or "Equal",
            "value": item.get("value") or "",
            "effect": item.get("effect") or "",
            "tolerationSeconds": item.get("tolerationSeconds"),
        }
        for item in items or []
    ]


def _managed_labels(annotations):
    value = json.loads(annotations.get(MANAGED_POD_LABELS_ANNOTATION, "[]"))
    if not isinstance(value, list) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"Invalid {MANAGED_POD_LABELS_ANNOTATION} annotation")
    return set(value) - STOWAWAY_LABELS.keys()


def stowaway_patch(current, desired) -> list[dict]:
    serialize = ApiClient().sanitize_for_serialization
    live = serialize(current)
    target = serialize(desired)
    operations = []

    def set_field(parent, path, key, value):
        if parent.get(key) != value:
            operations.append(
                {
                    "op": "replace" if key in parent else "add",
                    "path": f"{path}/{key}",
                    "value": value,
                }
            )

    live_meta = live["metadata"]
    annotations = live_meta.get("annotations") or {}
    desired_annotations = target["metadata"].get("annotations") or {}
    previous_labels = _managed_labels(annotations)
    desired_labels = _managed_labels(desired_annotations)
    template = live["spec"]["template"]
    target_template = target["spec"]["template"]
    template_meta = template.get("metadata") or {}
    labels = dict(template_meta.get("labels") or {})
    for key in previous_labels - desired_labels:
        labels.pop(key, None)
    labels.update(target_template["metadata"]["labels"])
    set_field(template_meta, "/spec/template/metadata", "labels", labels)

    next_annotations = dict(annotations)
    if desired_labels:
        next_annotations[MANAGED_POD_LABELS_ANNOTATION] = json.dumps(
            sorted(desired_labels)
        )
    else:
        next_annotations.pop(MANAGED_POD_LABELS_ANNOTATION, None)
    if next_annotations != annotations:
        set_field(live_meta, "/metadata", "annotations", next_annotations)

    spec = template["spec"]
    target_spec = target_template["spec"]
    if (spec.get("nodeSelector") or {}) != target_spec["nodeSelector"]:
        set_field(
            spec, "/spec/template/spec", "nodeSelector", target_spec["nodeSelector"]
        )
    if _tolerations(spec.get("tolerations")) != _tolerations(
        target_spec["tolerations"]
    ):
        set_field(
            spec, "/spec/template/spec", "tolerations", target_spec["tolerations"]
        )

    container_index, container = next(
        (index, item)
        for index, item in enumerate(spec["containers"])
        if item["name"] == "stowaway"
    )
    target_container = target_spec["containers"][0]
    container_path = f"/spec/template/spec/containers/{container_index}"
    set_field(container, container_path, "image", target_container["image"])
    probe = container.get("startupProbe")
    desired_probe = target_container["startupProbe"]
    if not probe:
        set_field(container, container_path, "startupProbe", desired_probe)
    elif probe.get("failureThreshold", 3) != desired_probe["failureThreshold"]:
        set_field(
            probe,
            f"{container_path}/startupProbe",
            "failureThreshold",
            desired_probe["failureThreshold"],
        )

    if operations:
        # Do not overwrite admission/controller changes made since the read.
        operations.insert(
            0,
            {
                "op": "test",
                "path": "/metadata/resourceVersion",
                "value": live_meta["resourceVersion"],
            },
        )
    return operations
