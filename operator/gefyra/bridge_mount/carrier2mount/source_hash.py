"""Idempotency helpers: hash the "meaningful" parts of the source workload /
HPA so re-reconciliations don't needlessly patch the shadow deployment.

A patch triggers a rolling restart of the shadow pods — expensive for
workloads with long startup (e.g. JVM apps) and pointless if nothing on the
source that actually matters for the shadow has changed. The hashes are
persisted as annotations on the shadow object, so they survive operator
restarts.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from kubernetes.client import ApiClient

SOURCE_WORKLOAD_HASH_ANNOTATION = "gefyra.dev/source-spec-hash"
SOURCE_HPA_HASH_ANNOTATION = "gefyra.dev/source-hpa-spec-hash"

_api_client = ApiClient()


def _to_plain(obj: Any) -> Any:
    return _api_client.sanitize_for_serialization(obj)


def _strip_volatile(payload: Any) -> Any:
    """Drop keys that change on every apiserver read but don't describe what
    the workload *is* (bookkeeping / server-set fields)."""
    _VOLATILE_METADATA_KEYS = (
        "resourceVersion",
        "uid",
        "generation",
        "creationTimestamp",
        "managedFields",
        "selfLink",
        "ownerReferences",
    )
    if isinstance(payload, dict):
        meta = payload.get("metadata")
        if isinstance(meta, dict):
            for key in _VOLATILE_METADATA_KEYS:
                meta.pop(key, None)
        for value in payload.values():
            _strip_volatile(value)
    elif isinstance(payload, list):
        for value in payload:
            _strip_volatile(value)
    return payload


def _digest(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


def hash_workload_source(workload) -> str:
    """Hash the pod template (for Deployments/StatefulSets) or pod spec (for
    bare Pods). Intentionally excludes ``spec.replicas``, ``status`` and any
    volatile server-side metadata so HPA-driven replica changes on the source
    don't trigger shadow churn."""
    spec = getattr(workload, "spec", None)
    template = getattr(spec, "template", None) if spec is not None else None
    if template is not None:
        payload = _to_plain(template)
    else:
        # Pod target: hash the pod's own spec only (skip status/metadata).
        payload = {"spec": _to_plain(spec)} if spec is not None else {}
    _strip_volatile(payload)
    return _digest(payload)


def hash_hpa_source(hpa) -> str:
    """Hash the HPA spec minus ``scaleTargetRef.name`` (which intentionally
    differs between original and duplicate)."""
    spec = _to_plain(getattr(hpa, "spec", None)) or {}
    target_ref = spec.get("scaleTargetRef")
    if isinstance(target_ref, dict):
        target_ref.pop("name", None)
    return _digest(spec)
