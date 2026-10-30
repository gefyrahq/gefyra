import json
from copy import deepcopy
from unittest.mock import Mock, patch

import pytest
import kubernetes as k8s


def configuration():
    from gefyra.configuration import OperatorConfiguration

    return OperatorConfiguration()


def build(config=None):
    from gefyra.connection.stowaway.resources.statefulsets import (
        create_stowaway_statefulset,
    )
    from gefyra.stowaway_config import STOWAWAY_LABELS

    return create_stowaway_statefulset(STOWAWAY_LABELS, config or configuration())


def apply_patch(live, operations):
    import jsonpatch

    api = k8s.client.ApiClient()
    document = jsonpatch.apply_patch(api.sanitize_for_serialization(live), operations)
    return api._ApiClient__deserialize(document, "V1StatefulSet")


@pytest.mark.parametrize(
    "name,value",
    [
        ("GEFYRA_STOWAWAY_NODE_SELECTOR", "{"),
        ("GEFYRA_STOWAWAY_NODE_SELECTOR", "[]"),
        ("GEFYRA_STOWAWAY_NODE_SELECTOR", '{"pool":1}'),
        ("GEFYRA_STOWAWAY_POD_LABELS", '{"gefyra.dev/provider":"other"}'),
        ("GEFYRA_STOWAWAY_POD_LABELS", '{"bad/key/name":"x"}'),
        ("GEFYRA_STOWAWAY_TOLERATIONS", "{}"),
        ("GEFYRA_STOWAWAY_TOLERATIONS", '[{"operator":"Bad"}]'),
        (
            "GEFYRA_STOWAWAY_TOLERATIONS",
            '[{"key":"pool","effect":"NoExecute","tolerationSeconds":true}]',
        ),
        ("GEFYRA_STOWAWAY_STARTUP_PROBE_FAILURE_THRESHOLD", "0"),
        ("GEFYRA_STOWAWAY_STARTUP_PROBE_FAILURE_THRESHOLD", "true"),
        ("GEFYRA_STOWAWAY_STARTUP_PROBE_FAILURE_THRESHOLD", '"60"'),
    ],
)
def test_invalid_operator_environment(monkeypatch, name, value):
    from gefyra.configuration import OperatorConfiguration

    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        OperatorConfiguration()


def test_environment_reaches_pod_template(monkeypatch):
    from gefyra.stowaway_config import STOWAWAY_LABELS

    baseline = dict(STOWAWAY_LABELS)
    monkeypatch.setenv("GEFYRA_STOWAWAY_NODE_SELECTOR", '{"example.com/pool":"gefyra"}')
    monkeypatch.setenv(
        "GEFYRA_STOWAWAY_POD_LABELS", '{"custom":"added", "gefyra.dev/app":"stowaway"}'
    )
    tolerations = [
        {
            "key": "pool",
            "operator": "Exists",
            "effect": "NoExecute",
            "tolerationSeconds": 30,
        },
        {"key": "pool", "value": "gefyra", "effect": "NoSchedule"},
    ]
    monkeypatch.setenv("GEFYRA_STOWAWAY_TOLERATIONS", json.dumps(tolerations))
    monkeypatch.setenv("GEFYRA_STOWAWAY_STARTUP_PROBE_FAILURE_THRESHOLD", "60")
    sts = build()
    serialized = k8s.client.ApiClient().sanitize_for_serialization(sts)
    spec = serialized["spec"]["template"]["spec"]
    assert spec["nodeSelector"] == {"example.com/pool": "gefyra"}
    assert spec["tolerations"][0]["tolerationSeconds"] == 30
    assert spec["tolerations"][1]["operator"] == "Equal"
    assert spec["containers"][0]["startupProbe"]["failureThreshold"] == 60
    assert sts.spec.template.metadata.labels == {**baseline, "custom": "added"}
    assert sts.spec.selector == {"matchLabels": baseline}
    assert STOWAWAY_LABELS == baseline


def test_default_legacy_statefulset_needs_no_update():
    from gefyra.connection.stowaway.reconciliation import stowaway_patch

    desired = build()
    live = deepcopy(desired)
    live.metadata.resource_version = "123"
    live.spec.template.spec.node_selector = None
    live.spec.template.spec.tolerations = None
    live.spec.template.spec.containers[0].startup_probe.failure_threshold = None
    assert stowaway_patch(live, desired) == []


def test_update_and_reset_preserve_storage_selectors_and_external_metadata():
    from gefyra.connection.stowaway.reconciliation import stowaway_patch
    from gefyra.connection.stowaway.resources.statefulsets import (
        MANAGED_POD_LABELS_ANNOTATION,
    )

    live = build()
    live.metadata.resource_version = "123"
    live.metadata.uid = "keep-this-uid"
    live.metadata.annotations = {"external": "keep"}
    live.spec.template.metadata.labels["external.example/label"] = "keep"
    live.spec.template.metadata.annotations = {"external": "keep"}
    live.spec.template.spec.containers.insert(
        0, k8s.client.V1Container(name="sidecar", image="sidecar:v1")
    )
    live.spec.template.spec.containers[1].startup_probe.timeout_seconds = 7
    original = deepcopy(live)
    config = configuration()
    config.STOWAWAY_NODE_SELECTOR = {"pool": "new"}
    config.STOWAWAY_TOLERATIONS = [{"operator": "Exists", "effect": "NoSchedule"}]
    config.STOWAWAY_POD_LABELS = {"example.com/managed": "new"}
    config.STOWAWAY_STARTUP_PROBE_FAILURE_THRESHOLD = 60
    config.STOWAWAY_TAG = "new"
    desired = build(config)
    operations = stowaway_patch(live, desired)
    assert operations[0] == {
        "op": "test",
        "path": "/metadata/resourceVersion",
        "value": "123",
    }
    updated = apply_patch(live, operations)
    assert updated.metadata.uid == original.metadata.uid
    serialize = k8s.client.ApiClient().sanitize_for_serialization
    assert serialize(updated.spec.volume_claim_templates) == serialize(
        original.spec.volume_claim_templates
    )
    assert serialize(updated.spec.selector) == serialize(original.spec.selector)
    assert updated.metadata.annotations["external"] == "keep"
    assert (
        updated.spec.template.metadata.annotations
        == original.spec.template.metadata.annotations
    )
    assert updated.spec.template.metadata.labels["external.example/label"] == "keep"
    assert updated.spec.template.metadata.labels["example.com/managed"] == "new"
    assert json.loads(updated.metadata.annotations[MANAGED_POD_LABELS_ANNOTATION]) == [
        "example.com/managed"
    ]
    assert (
        updated.spec.template.spec.containers[0]
        == original.spec.template.spec.containers[0]
    )
    assert updated.spec.template.spec.containers[1].startup_probe.timeout_seconds == 7
    assert (
        updated.spec.template.spec.containers[1].startup_probe.failure_threshold == 60
    )
    assert stowaway_patch(updated, desired) == []
    reset = apply_patch(updated, stowaway_patch(updated, build()))
    assert reset.spec.template.spec.node_selector == {}
    assert reset.spec.template.spec.tolerations == []
    assert reset.spec.template.spec.containers[1].startup_probe.failure_threshold == 3
    assert "example.com/managed" not in reset.spec.template.metadata.labels
    assert reset.spec.template.metadata.labels["external.example/label"] == "keep"
    assert reset.metadata.annotations == {"external": "keep"}
    assert stowaway_patch(reset, build()) == []


def test_reconciliation_handles_api_defaults():
    from gefyra.connection.stowaway.reconciliation import stowaway_patch

    config = configuration()
    config.STOWAWAY_TOLERATIONS = [{"key": "pool", "value": "gefyra"}]
    desired = build(config)
    live = deepcopy(desired)
    live.metadata.resource_version = "123"
    live.spec.template.spec.tolerations[0].effect = ""
    assert stowaway_patch(live, desired) == []


def test_resource_version_guard_rejects_stale_update():
    import jsonpatch
    from gefyra.connection.stowaway.reconciliation import stowaway_patch

    live = build()
    live.metadata.resource_version = "123"
    config = configuration()
    config.STOWAWAY_NODE_SELECTOR = {"pool": "new"}
    operations = stowaway_patch(live, build(config))
    live.metadata.resource_version = "124"
    with pytest.raises(jsonpatch.JsonPatchTestFailed):
        apply_patch(live, operations)


@pytest.mark.asyncio
async def test_check_updates_existing_statefulset_without_recreating():
    from gefyra.connection.stowaway import components
    from gefyra.stowaway_config import STOWAWAY_LABELS

    live = build()
    live.metadata.resource_version = "123"
    config = configuration()
    config.STOWAWAY_NODE_SELECTOR = {"pool": "new"}
    with patch.object(components, "app") as api:
        api.read_namespaced_stateful_set.return_value = live
        assert await components.check_stowaway_statefulset(
            Mock(), config, STOWAWAY_LABELS
        )
        api.patch_namespaced_stateful_set.assert_called_once()
        api.delete_namespaced_stateful_set.assert_not_called()
        api.create_namespaced_stateful_set.assert_not_called()
        updated = apply_patch(
            live, api.patch_namespaced_stateful_set.call_args.kwargs["body"]
        )
        api.read_namespaced_stateful_set.return_value = updated
        api.patch_namespaced_stateful_set.reset_mock()
        assert await components.check_stowaway_statefulset(
            Mock(), config, STOWAWAY_LABELS
        )
        api.patch_namespaced_stateful_set.assert_not_called()


def test_adopting_existing_label_only_updates_bookkeeping():
    from gefyra.connection.stowaway.reconciliation import stowaway_patch

    live = build()
    live.metadata.resource_version = "123"
    live.spec.template.metadata.labels["custom"] = "already-present"
    config = configuration()
    config.STOWAWAY_POD_LABELS = {"custom": "already-present"}
    desired = build(config)
    operations = stowaway_patch(live, desired)
    assert len(operations) == 2
    assert operations[1]["path"] == "/metadata/annotations"
    assert stowaway_patch(apply_patch(live, operations), desired) == []


@pytest.mark.asyncio
async def test_creation_conflict_reconciles_existing_statefulset():
    from gefyra.connection.stowaway import components
    from gefyra.stowaway_config import STOWAWAY_LABELS

    live = build()
    live.metadata.resource_version = "123"
    config = configuration()
    config.STOWAWAY_STARTUP_PROBE_FAILURE_THRESHOLD = 60
    with patch.object(components, "app") as api:
        api.create_namespaced_stateful_set.side_effect = (
            components.k8s.client.ApiException(status=409)
        )
        api.read_namespaced_stateful_set.return_value = live
        await components.handle_stowaway_statefulset(Mock(), config, STOWAWAY_LABELS)
        api.patch_namespaced_stateful_set.assert_called_once()
        updated = apply_patch(
            live, api.patch_namespaced_stateful_set.call_args.kwargs["body"]
        )
        assert (
            updated.spec.template.spec.containers[0].startup_probe.failure_threshold
            == 60
        )
        api.delete_namespaced_stateful_set.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [409, 422])
async def test_race_retries_from_fresh_metadata(status):
    from gefyra.connection.stowaway import components

    live = build()
    live.metadata.resource_version = "123"
    concurrent = deepcopy(live)
    concurrent.metadata.resource_version = "124"
    concurrent.spec.template.metadata.labels["external"] = "keep"
    config = configuration()
    config.STOWAWAY_POD_LABELS = {"custom": "new"}
    with patch.object(components, "app") as api:
        api.patch_namespaced_stateful_set.side_effect = [
            components.k8s.client.ApiException(status=status),
            None,
        ]
        api.read_namespaced_stateful_set.return_value = concurrent
        await components.reconcile_stowaway_statefulset(Mock(), live, build(config))
        assert api.patch_namespaced_stateful_set.call_count == 2
        update = api.patch_namespaced_stateful_set.call_args.kwargs
        assert update["_content_type"] == "application/json-patch+json"
        updated = apply_patch(concurrent, update["body"])
        assert updated.spec.template.metadata.labels["external"] == "keep"
        assert updated.spec.template.metadata.labels["custom"] == "new"


@pytest.mark.asyncio
async def test_validation_error_is_not_retried_without_resource_change():
    from gefyra.connection.stowaway import components

    live = build()
    live.metadata.resource_version = "123"
    config = configuration()
    config.STOWAWAY_NODE_SELECTOR = {"pool": "new"}
    with patch.object(components, "app") as api:
        api.patch_namespaced_stateful_set.side_effect = (
            components.k8s.client.ApiException(status=422)
        )
        api.read_namespaced_stateful_set.return_value = live
        with pytest.raises(components.k8s.client.ApiException):
            await components.reconcile_stowaway_statefulset(Mock(), live, build(config))
        api.patch_namespaced_stateful_set.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "observed,updated_revision,pod_revision,container_ready,expected",
    [
        (1, "new", "new", True, False),
        (2, "new", "old", True, False),
        (2, "new", "new", True, True),
        (2, "new", "new", False, False),
        (None, "new", "new", True, False),
        (2, None, "new", True, False),
        (2, "new", None, True, False),
    ],
)
async def test_readiness_waits_for_reconciled_pod(
    observed, updated_revision, pod_revision, container_ready, expected
):
    from unittest.mock import AsyncMock
    from gefyra.connection import stowaway

    live = build()
    live.metadata.generation = 2
    live.status = k8s.client.V1StatefulSetStatus(
        replicas=1, observed_generation=observed, update_revision=updated_revision
    )
    pod = k8s.client.V1Pod(
        metadata=k8s.client.V1ObjectMeta(
            labels={"controller-revision-hash": pod_revision}
        ),
        status=k8s.client.V1PodStatus(
            container_statuses=[
                k8s.client.V1ContainerStatus(
                    name="stowaway",
                    image="stowaway",
                    image_id="test",
                    restart_count=0,
                    ready=container_ready,
                )
            ]
        ),
    )
    provider = stowaway.Stowaway(configuration(), Mock())
    provider._get_stowaway_pod = AsyncMock(return_value=pod)
    with patch.object(stowaway, "app") as api:
        api.read_namespaced_stateful_set.return_value = live
        assert await provider.ready() is expected
