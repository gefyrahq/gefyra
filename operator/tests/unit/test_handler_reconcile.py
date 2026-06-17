"""Tests for the kopf timer reconcile handlers.

Regression coverage for the skip-guard that previously short-circuited the
reconciler whenever a GefyraBridgeMount / GefyraBridge had never reached
ACTIVE. Mounts stuck in PREPARING/INSTALLING (e.g. due to a transient error
during the initial install) would then never be progressed by the timer and
required an operator restart to recover.
"""

import logging
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

logger = logging.getLogger(__name__)


def _make_bridge_mount(state="PREPARING", state_transitions=None):
    data = {
        "apiVersion": "gefyra.dev/v1",
        "metadata": {
            "name": "test-mount",
            "namespace": "gefyra",
            "uid": "test-uid",
            "resourceVersion": "123",
        },
        "kind": "gefyrabridgemount",
        "state": state,
        "targetNamespace": "default",
        "target": "deploy/nginx",
        "targetContainer": "nginx",
        "provider": "carrier2mount",
    }
    if state_transitions is not None:
        data["stateTransitions"] = state_transitions
    return data


def _make_bridge(state="INSTALLING", state_transitions=None):
    data = {
        "apiVersion": "gefyra.dev/v1",
        "metadata": {
            "name": "test-bridge",
            "namespace": "gefyra",
            "uid": "bridge-uid",
            "resourceVersion": "1",
        },
        "kind": "gefyrabridge",
        "state": state,
        "targetNamespace": "default",
        "target": "nginx-pod/nginx",
        "targetContainer": "nginx",
        "targetContainerPorts": [{"containerPort": 80}],
        "destinationIP": "10.0.0.1",
        "connectionProvider": "stowaway",
        "client": "client-1",
        "port_mappings": [],
    }
    if state_transitions is not None:
        data["stateTransitions"] = state_transitions
    return data


class TestBridgeMountReconcileNotSkipped(IsolatedAsyncioTestCase):
    """The reconcile timer must drive non-ACTIVE mounts forward.

    Regression: previously the handler early-returned whenever
    stateTransitions["ACTIVE"] was missing, leaving mounts stuck in
    PREPARING/INSTALLING until the operator was restarted.
    """

    async def _run_reconcile(self, body, provider_mock):
        from gefyra.handler import bridge_mounts

        with patch.object(
            bridge_mounts.GefyraBridgeMount,
            "bridge_mount_provider",
            new=provider_mock,
        ), patch.object(
            bridge_mounts.GefyraBridgeMount,
            "post_event",
            new=AsyncMock(),
        ), patch.object(
            bridge_mounts.GefyraBridgeMountObject,
            "_write_state",
            new=MagicMock(),
        ):
            await bridge_mounts.bridge_mount_reconcile(body=body, logger=logger)

    async def test_preparing_mount_without_active_transition_is_reconciled(self):
        """Mount stuck in PREPARING and never reached ACTIVE must not be skipped."""
        from gefyra.handler import bridge_mounts

        body = _make_bridge_mount(state="PREPARING", state_transitions={})

        provider = MagicMock()
        provider.target_exists = AsyncMock(return_value=True)
        provider.prepared = AsyncMock(return_value=True)
        provider.ready = AsyncMock(return_value=False)
        provider.install = AsyncMock()
        provider.validate = MagicMock()

        with patch.object(
            bridge_mounts.GefyraBridgeMount, "install", new=AsyncMock()
        ) as install_mock, patch.object(
            bridge_mounts.GefyraBridgeMount,
            "bridge_mount_provider",
            new=provider,
        ), patch.object(
            bridge_mounts.GefyraBridgeMount,
            "post_event",
            new=AsyncMock(),
        ), patch.object(
            bridge_mounts.GefyraBridgeMountObject,
            "_write_state",
            new=MagicMock(),
        ):
            await bridge_mounts.bridge_mount_reconcile(body=body, logger=logger)

        install_mock.assert_awaited()

    async def test_installing_mount_without_active_transition_is_reconciled(self):
        """Mount stuck in INSTALLING and never reached ACTIVE must not be skipped."""
        from gefyra.handler import bridge_mounts

        body = _make_bridge_mount(state="INSTALLING", state_transitions={})

        provider = MagicMock()
        provider.target_exists = AsyncMock(return_value=True)
        provider.prepared = AsyncMock(return_value=True)
        provider.ready = AsyncMock(return_value=False)

        with patch.object(
            bridge_mounts.GefyraBridgeMount, "install", new=AsyncMock()
        ) as install_mock, patch.object(
            bridge_mounts.GefyraBridgeMount,
            "bridge_mount_provider",
            new=provider,
        ), patch.object(
            bridge_mounts.GefyraBridgeMount,
            "post_event",
            new=AsyncMock(),
        ), patch.object(
            bridge_mounts.GefyraBridgeMountObject,
            "_write_state",
            new=MagicMock(),
        ):
            await bridge_mounts.bridge_mount_reconcile(body=body, logger=logger)

        install_mock.assert_awaited()

    async def test_preparing_mount_skipped_when_shadow_not_prepared(self):
        """If the shadow is still syncing, install() must NOT be called yet."""
        from gefyra.handler import bridge_mounts

        body = _make_bridge_mount(state="PREPARING", state_transitions={})

        provider = MagicMock()
        provider.target_exists = AsyncMock(return_value=True)
        provider.prepared = AsyncMock(return_value=False)

        with patch.object(
            bridge_mounts.GefyraBridgeMount, "install", new=AsyncMock()
        ) as install_mock, patch.object(
            bridge_mounts.GefyraBridgeMount,
            "bridge_mount_provider",
            new=provider,
        ), patch.object(
            bridge_mounts.GefyraBridgeMount,
            "post_event",
            new=AsyncMock(),
        ), patch.object(
            bridge_mounts.GefyraBridgeMountObject,
            "_write_state",
            new=MagicMock(),
        ):
            await bridge_mounts.bridge_mount_reconcile(body=body, logger=logger)

        install_mock.assert_not_awaited()


class TestBridgeReconcileNotSkipped(IsolatedAsyncioTestCase):
    """Regression: bridge_reconcile must drive non-ACTIVE bridges forward."""

    async def test_installing_bridge_without_active_transition_is_reconciled(self):
        from gefyra.handler import bridges

        body = _make_bridge(state="INSTALLING", state_transitions={})

        with patch.object(
            bridges.GefyraBridge, "install", new=AsyncMock()
        ) as install_mock, patch.object(
            bridges.GefyraBridge, "activate", new=AsyncMock()
        ), patch.object(
            bridges.GefyraBridgeObject, "_write_state", new=MagicMock()
        ):
            await bridges.bridge_reconcile(body=body, logger=logger)

        install_mock.assert_awaited()
