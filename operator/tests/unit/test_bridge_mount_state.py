import logging
from datetime import datetime, timedelta, timezone
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from statemachine.exceptions import TransitionNotAllowed

from gefyra.configuration import OperatorConfiguration

logger = logging.getLogger(__name__)


def _make_bridge_mount(
    state="REQUESTED", missing_grace_period=None, state_transitions=None
):
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
    def test_missing_grace_period_uses_per_resource(self):
        bm = _make_bridge_mount(missing_grace_period=3600)
        assert bm.missing_grace_period == 3600

    def test_missing_grace_period_falls_back_to_global(self):
        bm = _make_bridge_mount()
        assert bm.missing_grace_period == 86400  # default 1 day

    def test_missing_grace_period_expired_true(self):
        two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        bm = _make_bridge_mount(state_transitions={"MISSING": two_days_ago})
        assert bm.missing_grace_period_expired is True

    def test_missing_grace_period_not_expired(self):
        just_now = datetime.now(timezone.utc).isoformat()
        bm = _make_bridge_mount(state_transitions={"MISSING": just_now})
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
        from kubernetes.client import ApiException

        mock_core_v1_api.read_namespace.side_effect = ApiException(status=403)
        bm = _make_bridge_mount()
        with self.assertRaises(ApiException):
            await bm.bridge_mount_provider.target_exists()

    @patch("gefyra.bridge_mount.carrier2mount.core_v1_api")
    async def test_target_exists_namespace_500_raises(self, mock_core_v1_api):
        from kubernetes.client import ApiException

        mock_core_v1_api.read_namespace.side_effect = ApiException(status=500)
        bm = _make_bridge_mount()
        with self.assertRaises(ApiException):
            await bm.bridge_mount_provider.target_exists()

    @patch("gefyra.bridge_mount.carrier2mount.core_v1_api")
    @patch("gefyra.bridge_mount.carrier2mount.app")
    async def test_target_exists_workload_403_raises(self, mock_app, mock_core_v1_api):
        from kubernetes.client import ApiException

        mock_app.read_namespaced_deployment.side_effect = ApiException(status=403)
        bm = _make_bridge_mount()
        with self.assertRaises(RuntimeError):
            await bm.bridge_mount_provider.target_exists()

    @patch("gefyra.bridge_mount.carrier2mount.core_v1_api")
    @patch("gefyra.bridge_mount.carrier2mount.app")
    async def test_target_exists_workload_500_raises(self, mock_app, mock_core_v1_api):
        from kubernetes.client import ApiException

        mock_app.read_namespaced_deployment.side_effect = ApiException(status=500)
        bm = _make_bridge_mount()
        with self.assertRaises(RuntimeError):
            await bm.bridge_mount_provider.target_exists()


class TestBridgeMountTargetExistsStateMachine(IsolatedAsyncioTestCase):
    @patch("gefyra.bridge_mount.carrier2mount.core_v1_api")
    async def test_state_machine_target_exists_returns_false_on_namespace_403(
        self, mock_core_v1_api
    ):
        from kubernetes.client import ApiException

        mock_core_v1_api.read_namespace.side_effect = ApiException(status=403)
        bm = _make_bridge_mount()
        assert await bm.target_exists is False

    @patch("gefyra.bridge_mount.carrier2mount.core_v1_api")
    async def test_state_machine_target_exists_returns_false_on_namespace_500(
        self, mock_core_v1_api
    ):
        from kubernetes.client import ApiException

        mock_core_v1_api.read_namespace.side_effect = ApiException(status=500)
        bm = _make_bridge_mount()
        assert await bm.target_exists is False

    @patch("gefyra.bridge_mount.carrier2mount.core_v1_api")
    @patch("gefyra.bridge_mount.carrier2mount.app")
    async def test_state_machine_target_exists_returns_false_on_workload_403(
        self, mock_app, mock_core_v1_api
    ):
        from kubernetes.client import ApiException

        mock_app.read_namespaced_deployment.side_effect = ApiException(status=403)
        bm = _make_bridge_mount()
        assert await bm.target_exists is False

    @patch("gefyra.bridge_mount.carrier2mount.core_v1_api")
    @patch("gefyra.bridge_mount.carrier2mount.app")
    async def test_state_machine_target_exists_returns_false_on_workload_500(
        self, mock_app, mock_core_v1_api
    ):
        from kubernetes.client import ApiException

        mock_app.read_namespaced_deployment.side_effect = ApiException(status=500)
        bm = _make_bridge_mount()
        assert await bm.target_exists is False


class TestBridgeMountRestoreFromInstalling(IsolatedAsyncioTestCase):
    """Tests for the new installing → restoring and preparing → restoring transitions."""

    async def test_restore_from_installing(self):
        bm = _make_bridge_mount(state="INSTALLING")
        # Mock prepare() so on_restore → on_arrange doesn't hit K8s API
        bm.bridge_mount_provider.prepare = AsyncMock()
        await bm.send("restore")
        # restore → on_restore → arrange → on_arrange → prepare (mocked)
        # Ends up in PREPARING
        assert bm.preparing.is_active

    async def test_restore_from_preparing(self):
        bm = _make_bridge_mount(state="PREPARING")
        bm.bridge_mount_provider.prepare = AsyncMock()
        await bm.send("restore")
        assert bm.preparing.is_active

    async def test_restore_from_terminated_raises(self):
        bm = _make_bridge_mount(state="TERMINATED")
        with self.assertRaises(TransitionNotAllowed):
            await bm.send("restore")


class TestBridgeMountReplicaSyncRemoved(IsolatedAsyncioTestCase):
    """After GO-1030, the operator no longer follows the original deployment's
    replica count. The duplicated HPA owns the shadow's scaling decisions, so
    prepared()/ready() must not react to replica mismatches."""

    def test_scale_shadow_to_match_helper_is_gone(self):
        from gefyra.bridge_mount.carrier2mount import Carrier2BridgeMount

        assert not hasattr(Carrier2BridgeMount, "_scale_shadow_to_match")

    async def test_prepared_ignores_replica_mismatch(self):
        """Original has 1 pod, shadow has 2 ready pods. prepared() returns True
        and no scaling helper is invoked."""
        from tests.factories import NginxPodFactory, V1PodListFactory

        original_pods = V1PodListFactory(
            items=[NginxPodFactory(metadata__name="nginx-original-1")]
        )
        gefyra_pods = V1PodListFactory(
            items=[
                NginxPodFactory(metadata__name="nginx-gefyra-1"),
                NginxPodFactory(metadata__name="nginx-gefyra-2"),
            ]
        )

        bm = _make_bridge_mount(state="INSTALLING")
        provider = bm.bridge_mount_provider
        original_target = "deploy/nginx"

        async def mock_get_pods(name, namespace):
            if name == original_target:
                return original_pods
            return gefyra_pods

        async def mock_healthy(pod, container_name):
            return True

        provider.get_pods_workload = mock_get_pods
        provider.pod_ready_and_healthy = mock_healthy

        result = await provider.prepared()
        assert result is True

    async def test_prepared_returns_false_when_shadow_pods_not_ready(self):
        from tests.factories import NginxPodFactory, V1PodListFactory

        gefyra_pods = V1PodListFactory(
            items=[NginxPodFactory(metadata__name="nginx-gefyra-1")]
        )

        bm = _make_bridge_mount(state="INSTALLING")
        provider = bm.bridge_mount_provider

        async def mock_get_pods(name, namespace):
            return gefyra_pods

        async def mock_healthy(pod, container_name):
            return False

        provider.get_pods_workload = mock_get_pods
        provider.pod_ready_and_healthy = mock_healthy

        result = await provider.prepared()
        assert result is False

    async def test_ready_ignores_replica_mismatch(self):
        from tests.factories import NginxPodFactory, V1PodListFactory

        original_pods = V1PodListFactory(
            items=[NginxPodFactory(metadata__name="nginx-original-1")]
        )
        gefyra_pods = V1PodListFactory(
            items=[
                NginxPodFactory(metadata__name="nginx-gefyra-1"),
                NginxPodFactory(metadata__name="nginx-gefyra-2"),
            ]
        )

        bm = _make_bridge_mount(state="ACTIVE")
        provider = bm.bridge_mount_provider
        original_target = "deploy/nginx"

        async def mock_get_pods(name, namespace):
            if name == original_target:
                return original_pods
            return gefyra_pods

        async def mock_healthy(pod, container_name):
            return True

        provider.get_pods_workload = mock_get_pods
        provider.pod_ready_and_healthy = mock_healthy

        with patch.object(
            type(provider),
            "_carrier_installed",
            new=_async_property(True),
        ), patch.object(
            type(provider),
            "_upstream_set",
            new=_async_property(True),
        ):
            assert await provider.ready() is True


def _async_property(value):
    """Build an awaitable property descriptor returning ``value``."""

    async def _coro(_self):
        return value

    return property(_coro)
