import logging
from datetime import datetime, timedelta, timezone
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, MagicMock, patch

import kopf
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


class TestBridgeMountRolloutRetry(IsolatedAsyncioTestCase):
    def _mixed_pods(self):
        from tests.factories import NginxPodFactory, V1PodListFactory

        return V1PodListFactory(
            items=[
                NginxPodFactory(metadata__owner_references__0__name="nginx-old"),
                NginxPodFactory(metadata__owner_references__0__name="nginx-new"),
            ]
        )

    async def test_prepare_waits_without_modifying_shadow_and_resumes(self):
        bm = _make_bridge_mount()
        provider = bm.bridge_mount_provider
        pods = self._mixed_pods()
        provider.get_pods_workload = AsyncMock(return_value=pods)
        provider._duplicate_workload = AsyncMock()

        for _ in range(3):
            with self.assertRaises(kopf.TemporaryError):
                await provider.prepare()
        provider._duplicate_workload.assert_not_awaited()

        pods.items.pop(0)
        await provider.prepare()
        provider._duplicate_workload.assert_awaited_once()

    async def test_prepare_read_failure_does_not_modify_shadow(self):
        from gefyra.bridge_mount.exceptions import BridgeMountInstallException

        bm = _make_bridge_mount()
        provider = bm.bridge_mount_provider
        provider.get_pods_workload = AsyncMock(side_effect=RuntimeError("API error"))
        provider._duplicate_workload = AsyncMock()

        with self.assertRaises(BridgeMountInstallException):
            await provider.prepare()
        provider._duplicate_workload.assert_not_awaited()

    async def test_prepare_does_not_add_readiness_or_workload_type_restrictions(self):
        from tests.factories import NginxPodFactory, V1PodListFactory

        for target in ("deploy/nginx", "sts/nginx", "pod/nginx"):
            with self.subTest(target=target):
                bm = _make_bridge_mount()
                provider = bm.bridge_mount_provider
                provider.target = target
                # A single controller is allowed even when its Pod is unready.
                pod = NginxPodFactory(status__phase="Pending")
                provider.get_pods_workload = AsyncMock(
                    return_value=V1PodListFactory(items=[pod])
                )
                provider._duplicate_workload = AsyncMock()
                await provider.prepare()
                provider._duplicate_workload.assert_awaited_once()

    async def test_install_race_waits_without_impairing_or_patching_originals(self):
        from gefyra.bridge_mount import carrier2mount

        bm = _make_bridge_mount(state="PREPARING")
        provider = bm.bridge_mount_provider
        provider.get_pods_workload = AsyncMock(return_value=self._mixed_pods())
        provider.pod_ready_and_healthy = AsyncMock(return_value=True)
        with patch.object(carrier2mount, "core_v1_api") as core:
            with self.assertRaises(kopf.TemporaryError):
                await bm.install()
            core.patch_namespaced_pod.assert_not_called()
            core.patch_namespaced_config_map.assert_not_called()
            core.create_namespaced_config_map.assert_not_called()
        assert not bm.error.is_active

        provider.install = AsyncMock()
        provider.ready = AsyncMock(return_value=True)
        await bm.install()
        assert bm.active.is_active

    async def test_real_install_failure_still_impairs(self):
        from gefyra.bridge.exceptions import BridgeInstallException

        for error in (
            BridgeInstallException("Probes not compatible"),
            kopf.TemporaryError("Failed to patch Pod", delay=10),
        ):
            with self.subTest(error=type(error).__name__):
                bm = _make_bridge_mount(state="INSTALLING")
                bm.bridge_mount_provider.prepared = AsyncMock(return_value=True)
                bm.bridge_mount_provider.install = AsyncMock(side_effect=error)
                await bm.install()
                assert bm.error.is_active

    async def test_handlers_retry_with_fresh_mounts_and_resume_after_rollout(self):
        from copy import deepcopy

        from gefyra.bridge_mount_state import GefyraBridgeMount
        from gefyra.handler import bridge_mounts

        # Rebuild from persisted state on every invocation, as Kopf does.
        cases = (
            ("REQUESTED", False),
            ("ACTIVE", True),
            ("ERROR", True),
            ("RESTORING", True),
            ("PREPARING", False),
            ("INSTALLING", False),
            ("PREPARING", True),
            ("INSTALLING", True),
        )
        for initial, was_active in cases:
            with self.subTest(state=initial, was_active=was_active):
                body = deepcopy(_make_bridge_mount(state=initial).data)
                if was_active:
                    body["stateTransitions"] = {"ACTIVE": "2026-01-01T00:00:00Z"}
                pods = self._mixed_pods()
                duplicate = AsyncMock()

                def make_mount(obj, configuration, logger, initial):
                    bm = GefyraBridgeMount(obj, configuration, logger, initial=initial)
                    bm.post_event = AsyncMock()

                    def save_state(state):
                        body["state"] = str(state)
                        body.setdefault("stateTransitions", {})[str(state)] = (
                            "2026-01-01T00:00:00Z"
                        )

                    obj._write_state = MagicMock(side_effect=save_state)
                    provider = bm.bridge_mount_provider
                    provider.get_pods_workload = AsyncMock(return_value=pods)
                    provider.pod_ready_and_healthy = AsyncMock(return_value=True)
                    provider._duplicate_workload = duplicate
                    provider.target_exists = AsyncMock(return_value=True)
                    provider.ready = AsyncMock(return_value=False)
                    if len(pods.items) == 1:
                        provider.install = AsyncMock()
                        provider.ready.return_value = True
                    return bm

                handler = (
                    bridge_mounts.bridge_mount_reconcile
                    if was_active
                    else bridge_mounts.bridge_mount_created
                )
                with patch.object(
                    bridge_mounts, "GefyraBridgeMount", side_effect=make_mount
                ) as mount_class:
                    mount_class.active = GefyraBridgeMount.active
                    for _ in range(3):
                        with self.assertRaises(kopf.TemporaryError):
                            await handler(body, logger)
                    duplicate.assert_not_awaited()
                    assert "ERROR" not in body.get("stateTransitions", {})

                    pods.items.pop(0)
                    await handler(body, logger)
                    assert body["state"] == "ACTIVE"
                    if initial in ("PREPARING", "INSTALLING"):
                        duplicate.assert_not_awaited()
                    else:
                        duplicate.assert_awaited_once()

    async def test_delete_does_not_wait_for_rollout(self):
        from gefyra.handler import bridge_mounts

        bm = _make_bridge_mount(state="PREPARING")
        bm.bridge_mount_provider.uninstall = AsyncMock()
        bm.cleanup_all_bridges = AsyncMock()
        with patch.object(bridge_mounts, "GefyraBridgeMount", return_value=bm):
            await bridge_mounts.bridgemount_deleted(bm.data, logger)
        assert bm.terminated.is_active
        bm.bridge_mount_provider.uninstall.assert_awaited_once()
