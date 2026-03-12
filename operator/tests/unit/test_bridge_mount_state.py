import logging
from datetime import datetime, timedelta, timezone
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from statemachine.exceptions import TransitionNotAllowed

from gefyra.configuration import OperatorConfiguration

logger = logging.getLogger(__name__)


def _make_bridge_mount(state="REQUESTED", missing_grace_period=None, state_transitions=None):
    """
    Factory helper that creates a GefyraBridgeMount state machine instance
    for testing, with ``_write_state`` and ``post_event`` mocked out so no
    K8s API calls are made.

    :param state: Initial state value (e.g. "REQUESTED", "ACTIVE", "MISSING").
    :param missing_grace_period: Optional per-resource grace period override (seconds).
    :param state_transitions: Optional dict of state transition timestamps,
        e.g. ``{"MISSING": "2025-01-01T00:00:00"}``.
    :return: A configured GefyraBridgeMount instance ready for assertions.
    """
    from gefyra.bridge_mount_state import GefyraBridgeMount, GefyraBridgeMountObject

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
    if missing_grace_period is not None:
        data["missingGracePeriod"] = missing_grace_period
    if state_transitions is not None:
        data["stateTransitions"] = state_transitions

    obj = GefyraBridgeMountObject(data)
    obj._write_state = MagicMock()
    configuration = OperatorConfiguration()
    bridge_mount = GefyraBridgeMount(obj, configuration, logger, initial=state)
    bridge_mount.post_event = AsyncMock()
    return bridge_mount


class TestBridgeMountMissingState(IsolatedAsyncioTestCase):
    """Test the MISSING state transitions in the GefyraBridgeMount state machine."""

    async def test_mark_missing_from_active(self):
        bm = _make_bridge_mount(state="ACTIVE")
        bm.bridge_mount_provider.uninstall = AsyncMock()
        await bm.mark_missing()
        assert bm.missing.is_active

    async def test_mark_missing_from_error(self):
        bm = _make_bridge_mount(state="ERROR")
        bm.bridge_mount_provider.uninstall = AsyncMock()
        await bm.mark_missing()
        assert bm.missing.is_active

    async def test_mark_missing_from_restoring(self):
        bm = _make_bridge_mount(state="RESTORING")
        bm.bridge_mount_provider.uninstall = AsyncMock()
        await bm.mark_missing()
        assert bm.missing.is_active

    async def test_mark_missing_from_preparing(self):
        bm = _make_bridge_mount(state="PREPARING")
        bm.bridge_mount_provider.uninstall = AsyncMock()
        await bm.mark_missing()
        assert bm.missing.is_active

    async def test_mark_missing_from_installing(self):
        bm = _make_bridge_mount(state="INSTALLING")
        bm.bridge_mount_provider.uninstall = AsyncMock()
        await bm.mark_missing()
        assert bm.missing.is_active

    async def test_mark_missing_from_requested(self):
        bm = _make_bridge_mount(state="REQUESTED")
        bm.bridge_mount_provider.uninstall = AsyncMock()
        await bm.mark_missing()
        assert bm.missing.is_active

    async def test_mark_missing_from_terminated_raises(self):
        bm = _make_bridge_mount(state="TERMINATED")
        with self.assertRaises(TransitionNotAllowed):
            await bm.mark_missing()

    async def test_mark_missing_from_missing_raises(self):
        bm = _make_bridge_mount(state="MISSING")
        with self.assertRaises(TransitionNotAllowed):
            await bm.mark_missing()

    async def test_recover_from_missing(self):
        bm = _make_bridge_mount(state="MISSING")
        await bm.recover()
        assert bm.preparing.is_active

    async def test_recover_from_non_missing_raises(self):
        bm = _make_bridge_mount(state="ACTIVE")
        with self.assertRaises(TransitionNotAllowed):
            await bm.recover()

    async def test_terminate_from_missing(self):
        bm = _make_bridge_mount(state="MISSING")
        bm.bridge_mount_provider.uninstall = AsyncMock()
        bm.cleanup_all_bridges = AsyncMock()
        await bm.terminate()
        assert bm.terminated.is_active


class TestBridgeMountGracePeriod(TestCase):
    """Test grace period resolution (per-resource vs global) and expiry logic."""

    def test_missing_grace_period_uses_per_resource(self):
        bm = _make_bridge_mount(missing_grace_period=3600)
        assert bm.missing_grace_period == 3600

    def test_missing_grace_period_falls_back_to_global(self):
        bm = _make_bridge_mount()
        assert bm.missing_grace_period == 86400  # default 1 day

    def test_missing_grace_period_expired_true(self):
        two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        bm = _make_bridge_mount(
            state_transitions={"MISSING": two_days_ago}
        )
        assert bm.missing_grace_period_expired is True

    def test_missing_grace_period_not_expired(self):
        just_now = datetime.now(timezone.utc).isoformat()
        bm = _make_bridge_mount(
            state_transitions={"MISSING": just_now}
        )
        assert bm.missing_grace_period_expired is False

    def test_missing_grace_period_expired_no_transition(self):
        bm = _make_bridge_mount()
        assert bm.missing_grace_period_expired is False

    def test_missing_grace_period_expired_with_custom_period(self):
        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        # grace period is 30 minutes = 1800s, so 1 hour ago should be expired
        bm = _make_bridge_mount(
            missing_grace_period=1800,
            state_transitions={"MISSING": one_hour_ago},
        )
        assert bm.missing_grace_period_expired is True

    def test_missing_grace_period_not_expired_with_custom_period(self):
        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        # grace period is 2 hours = 7200s, so 1 hour ago should NOT be expired
        bm = _make_bridge_mount(
            missing_grace_period=7200,
            state_transitions={"MISSING": one_hour_ago},
        )
        assert bm.missing_grace_period_expired is False


class TestBridgeMountTargetExists(IsolatedAsyncioTestCase):
    """Test the Carrier2BridgeMount.target_exists() method with mocked K8s API."""

    @patch("gefyra.bridge_mount.carrier2mount.core_v1_api")
    @patch("gefyra.bridge_mount.carrier2mount.app")
    async def test_target_exists_returns_true(self, mock_app, mock_core_v1_api):
        from tests.factories import NginxDeploymentFactory

        mock_app.read_namespaced_deployment.return_value = NginxDeploymentFactory()
        bm = _make_bridge_mount()
        assert await bm.bridge_mount_provider.target_exists() is True
        mock_core_v1_api.read_namespace.assert_called_once_with("default")
        mock_app.read_namespaced_deployment.assert_called_once()

    @patch("gefyra.bridge_mount.carrier2mount.core_v1_api")
    @patch("gefyra.bridge_mount.carrier2mount.app")
    async def test_target_exists_workload_404(self, mock_app, mock_core_v1_api):
        from kubernetes.client import ApiException

        mock_app.read_namespaced_deployment.side_effect = ApiException(status=404)
        bm = _make_bridge_mount()
        assert await bm.bridge_mount_provider.target_exists() is False

    @patch("gefyra.bridge_mount.carrier2mount.core_v1_api")
    async def test_target_exists_namespace_404(self, mock_core_v1_api):
        from kubernetes.client import ApiException

        mock_core_v1_api.read_namespace.side_effect = ApiException(status=404)
        bm = _make_bridge_mount()
        assert await bm.bridge_mount_provider.target_exists() is False

    @patch("gefyra.bridge_mount.carrier2mount.core_v1_api")
    async def test_target_exists_namespace_403_raises(self, mock_core_v1_api):
        """Non-404 errors (e.g. RBAC 403) must propagate from the provider layer."""
        from kubernetes.client import ApiException

        mock_core_v1_api.read_namespace.side_effect = ApiException(status=403)
        bm = _make_bridge_mount()
        with self.assertRaises(ApiException):
            await bm.bridge_mount_provider.target_exists()

    @patch("gefyra.bridge_mount.carrier2mount.core_v1_api")
    async def test_target_exists_namespace_500_raises(self, mock_core_v1_api):
        """Transient server errors must propagate from the provider layer."""
        from kubernetes.client import ApiException

        mock_core_v1_api.read_namespace.side_effect = ApiException(status=500)
        bm = _make_bridge_mount()
        with self.assertRaises(ApiException):
            await bm.bridge_mount_provider.target_exists()

    @patch("gefyra.bridge_mount.carrier2mount.core_v1_api")
    @patch("gefyra.bridge_mount.carrier2mount.app")
    async def test_target_exists_workload_403_raises(self, mock_app, mock_core_v1_api):
        """Non-404 on the workload read (AppsV1Api) must propagate as RuntimeError.

        _get_workload wraps non-404 ApiExceptions in a RuntimeError.
        """
        from kubernetes.client import ApiException

        mock_app.read_namespaced_deployment.side_effect = ApiException(status=403)
        bm = _make_bridge_mount()
        with self.assertRaises(RuntimeError):
            await bm.bridge_mount_provider.target_exists()

    @patch("gefyra.bridge_mount.carrier2mount.core_v1_api")
    @patch("gefyra.bridge_mount.carrier2mount.app")
    async def test_target_exists_workload_500_raises(self, mock_app, mock_core_v1_api):
        """Transient 500 on the workload read (AppsV1Api) must propagate as RuntimeError."""
        from kubernetes.client import ApiException

        mock_app.read_namespaced_deployment.side_effect = ApiException(status=500)
        bm = _make_bridge_mount()
        with self.assertRaises(RuntimeError):
            await bm.bridge_mount_provider.target_exists()


class TestBridgeMountTargetExistsStateMachine(IsolatedAsyncioTestCase):
    """Test the state-machine-level target_exists property.

    The state machine wraps the provider's target_exists() and catches *all*
    exceptions (including non-404 ApiExceptions) so that transient or RBAC
    failures don't block reconciliation. Instead it returns False and logs
    a warning — the reconciliation loop will retry on the next tick.
    """

    @patch("gefyra.bridge_mount.carrier2mount.core_v1_api")
    async def test_state_machine_target_exists_returns_false_on_namespace_403(self, mock_core_v1_api):
        """A 403 on namespace read becomes False at the state machine level."""
        from kubernetes.client import ApiException

        mock_core_v1_api.read_namespace.side_effect = ApiException(status=403)
        bm = _make_bridge_mount()
        assert await bm.target_exists is False

    @patch("gefyra.bridge_mount.carrier2mount.core_v1_api")
    async def test_state_machine_target_exists_returns_false_on_namespace_500(self, mock_core_v1_api):
        """A 500 on namespace read becomes False at the state machine level."""
        from kubernetes.client import ApiException

        mock_core_v1_api.read_namespace.side_effect = ApiException(status=500)
        bm = _make_bridge_mount()
        assert await bm.target_exists is False

    @patch("gefyra.bridge_mount.carrier2mount.core_v1_api")
    @patch("gefyra.bridge_mount.carrier2mount.app")
    async def test_state_machine_target_exists_returns_false_on_workload_403(self, mock_app, mock_core_v1_api):
        """A 403 on workload read (RuntimeError from _get_workload) becomes False."""
        from kubernetes.client import ApiException

        mock_app.read_namespaced_deployment.side_effect = ApiException(status=403)
        bm = _make_bridge_mount()
        assert await bm.target_exists is False

    @patch("gefyra.bridge_mount.carrier2mount.core_v1_api")
    @patch("gefyra.bridge_mount.carrier2mount.app")
    async def test_state_machine_target_exists_returns_false_on_workload_500(self, mock_app, mock_core_v1_api):
        """A 500 on workload read (RuntimeError from _get_workload) becomes False."""
        from kubernetes.client import ApiException

        mock_app.read_namespaced_deployment.side_effect = ApiException(status=500)
        bm = _make_bridge_mount()
        assert await bm.target_exists is False
