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


class TestBridgeMountHPAScaleScenario(IsolatedAsyncioTestCase):
    """Test that HPA scaling triggers shadow scaling instead of restore loops."""

    async def test_replica_mismatch_scales_shadow_from_installing(self):
        """Simulate HPA downscale: original has 1 pod, shadow still has 2.

        prepared() should scale the shadow to match and return False so the
        handler retries after pods have converged.
        """
        from tests.factories import NginxPodFactory, V1PodListFactory

        # Original workload: HPA scaled down to 1 pod
        original_pods = V1PodListFactory(
            items=[
                NginxPodFactory(metadata__name="nginx-original-1"),
            ]
        )
        # Shadow workload: still has 2 pods from before HPA
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

        provider.get_pods_workload = mock_get_pods
        provider._scale_shadow_to_match = AsyncMock()

        is_prepared = await provider.prepared()
        assert is_prepared is False
        provider._scale_shadow_to_match.assert_awaited_once_with(1)

    async def test_replica_mismatch_scales_shadow_from_preparing(self):
        """Same scenario but starting from PREPARING state."""
        from tests.factories import NginxPodFactory, V1PodListFactory

        original_pods = V1PodListFactory(
            items=[
                NginxPodFactory(metadata__name="nginx-original-1"),
            ]
        )
        gefyra_pods = V1PodListFactory(
            items=[
                NginxPodFactory(metadata__name="nginx-gefyra-1"),
                NginxPodFactory(metadata__name="nginx-gefyra-2"),
            ]
        )

        bm = _make_bridge_mount(state="PREPARING")
        provider = bm.bridge_mount_provider

        original_target = "deploy/nginx"

        async def mock_get_pods(name, namespace):
            if name == original_target:
                return original_pods
            return gefyra_pods

        provider.get_pods_workload = mock_get_pods
        provider._scale_shadow_to_match = AsyncMock()

        is_prepared = await provider.prepared()
        assert is_prepared is False
        provider._scale_shadow_to_match.assert_awaited_once_with(1)

    async def test_matching_replicas_prepared_returns_true(self):
        """When pod counts match and pods are ready, prepared() returns True."""
        from tests.factories import NginxPodFactory, V1PodListFactory

        pod = NginxPodFactory(metadata__name="nginx-1")
        pod_list = V1PodListFactory(items=[pod])

        bm = _make_bridge_mount(state="INSTALLING")
        provider = bm.bridge_mount_provider

        async def mock_get_pods(name, namespace):
            return pod_list

        provider.get_pods_workload = mock_get_pods

        async def mock_healthy(pod, container_name):
            return True

        provider.pod_ready_and_healthy = mock_healthy

        result = await provider.prepared()
        assert result is True
