import logging
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from gefyra.configuration import OperatorConfiguration
from gefyra.bridge_mount_state import GefyraBridgeMount, GefyraBridgeMountObject

logger = logging.getLogger(__name__)


def _make_bridge_mount_data(state="ACTIVE", restore_attempts=None, install_attempts=None):
    data = {
        "apiVersion": "gefyra.dev/v1",
        "kind": "GefyraBridgeMount",
        "metadata": {
            "name": "test-mount",
            "namespace": "gefyra",
            "uid": "test-uid",
            "resourceVersion": "1",
        },
        "state": state,
        "provider": "carrier2",
        "targetNamespace": "default",
        "target": "deploy/nginx",
        "targetContainer": "nginx",
    }
    status = {}
    if restore_attempts is not None:
        status["restoreAttempts"] = restore_attempts
    if install_attempts is not None:
        status["installAttempts"] = install_attempts
    if status:
        data["status"] = status
    return data


def _create_state_machine(state="ACTIVE", restore_attempts=None, install_attempts=None):
    data = _make_bridge_mount_data(
        state=state,
        restore_attempts=restore_attempts,
        install_attempts=install_attempts,
    )

    with patch("gefyra.base.k8s"):
        model = GefyraBridgeMountObject(data)

    config = OperatorConfiguration()
    sm = GefyraBridgeMount(
        model=model,
        configuration=config,
        logger=logger,
        initial=state,
    )
    sm._patch_object = AsyncMock()
    sm.post_event = AsyncMock()
    return sm


class TestRestoreCircuitBreaker(IsolatedAsyncioTestCase):
    async def test_restore_increments_counter(self):
        sm = _create_state_machine(restore_attempts=0)
        mock_provider = AsyncMock()
        mock_provider.prepare = AsyncMock()
        sm._bridge_mount_provider = mock_provider
        await sm.restore()
        sm._patch_object.assert_any_call({"status": {"restoreAttempts": 1}})

    async def test_restore_trips_after_max_attempts(self):
        config = OperatorConfiguration()
        max_attempts = config.BRIDGE_MOUNT_MAX_RESTORE_ATTEMPTS
        sm = _create_state_machine(restore_attempts=max_attempts - 1)
        await sm.restore()
        sm._patch_object.assert_any_call({"status": {"restoreAttempts": max_attempts}})
        self.assertEqual(sm.current_state.value, "ERROR")

    async def test_restore_continues_below_max(self):
        sm = _create_state_machine(restore_attempts=1)
        mock_provider = AsyncMock()
        mock_provider.prepare = AsyncMock()
        sm._bridge_mount_provider = mock_provider
        await sm.restore()
        self.assertEqual(sm.current_state.value, "PREPARING")

    async def test_backward_compat_missing_status(self):
        sm = _create_state_machine(restore_attempts=None)
        mock_provider = AsyncMock()
        mock_provider.prepare = AsyncMock()
        sm._bridge_mount_provider = mock_provider
        await sm.restore()
        sm._patch_object.assert_any_call({"status": {"restoreAttempts": 1}})
        self.assertEqual(sm.current_state.value, "PREPARING")

    async def test_restore_circuit_breaker_event_message(self):
        config = OperatorConfiguration()
        max_attempts = config.BRIDGE_MOUNT_MAX_RESTORE_ATTEMPTS
        sm = _create_state_machine(restore_attempts=max_attempts - 1)
        await sm.restore()
        calls = sm.post_event.call_args_list
        warning_calls = [c for c in calls if c.kwargs.get("type") == "Warning"]
        self.assertTrue(len(warning_calls) > 0)
        reason = warning_calls[0].kwargs.get("reason", "")
        self.assertIn("circuit breaker", reason.lower())
        msg = warning_calls[0].kwargs.get("message", "")
        self.assertIn("exceeded maximum restore attempts", msg.lower())


class TestInstallCircuitBreaker(IsolatedAsyncioTestCase):
    async def test_install_increments_counter(self):
        sm = _create_state_machine(state="INSTALLING", install_attempts=0)
        mock_provider = AsyncMock()
        mock_provider.prepared = AsyncMock(return_value=True)
        mock_provider.install = AsyncMock()
        mock_provider.ready = AsyncMock(return_value=True)
        sm._bridge_mount_provider = mock_provider
        await sm.install()
        sm._patch_object.assert_any_call({"status": {"installAttempts": 1}})

    async def test_install_trips_after_max_attempts(self):
        config = OperatorConfiguration()
        max_attempts = config.BRIDGE_MOUNT_MAX_RESTORE_ATTEMPTS
        sm = _create_state_machine(state="INSTALLING", install_attempts=max_attempts - 1)
        mock_provider = AsyncMock()
        mock_provider.prepared = AsyncMock(return_value=True)
        sm._bridge_mount_provider = mock_provider
        await sm.install()
        sm._patch_object.assert_any_call({"status": {"installAttempts": max_attempts}})
        self.assertEqual(sm.current_state.value, "ERROR")

    async def test_install_continues_below_max(self):
        sm = _create_state_machine(state="INSTALLING", install_attempts=1)
        mock_provider = AsyncMock()
        mock_provider.prepared = AsyncMock(return_value=True)
        mock_provider.install = AsyncMock()
        mock_provider.ready = AsyncMock(return_value=False)  # HPA mismatch
        sm._bridge_mount_provider = mock_provider
        await sm.install()
        # activate condition fails, stays INSTALLING
        self.assertEqual(sm.current_state.value, "INSTALLING")

    async def test_install_circuit_breaker_event_message(self):
        config = OperatorConfiguration()
        max_attempts = config.BRIDGE_MOUNT_MAX_RESTORE_ATTEMPTS
        sm = _create_state_machine(state="INSTALLING", install_attempts=max_attempts - 1)
        mock_provider = AsyncMock()
        mock_provider.prepared = AsyncMock(return_value=True)
        sm._bridge_mount_provider = mock_provider
        await sm.install()
        calls = sm.post_event.call_args_list
        warning_calls = [c for c in calls if c.kwargs.get("type") == "Warning"]
        self.assertTrue(len(warning_calls) > 0)
        reason = warning_calls[0].kwargs.get("reason", "")
        self.assertIn("circuit breaker", reason.lower())
        msg = warning_calls[0].kwargs.get("message", "")
        self.assertIn("exceeded maximum install attempts", msg.lower())

    async def test_install_backward_compat_missing_status(self):
        sm = _create_state_machine(state="INSTALLING", install_attempts=None)
        mock_provider = AsyncMock()
        mock_provider.prepared = AsyncMock(return_value=True)
        mock_provider.install = AsyncMock()
        mock_provider.ready = AsyncMock(return_value=True)
        sm._bridge_mount_provider = mock_provider
        await sm.install()
        sm._patch_object.assert_any_call({"status": {"installAttempts": 1}})


class TestActivateResetsCounters(IsolatedAsyncioTestCase):
    async def test_activate_resets_both_counters(self):
        sm = _create_state_machine(
            state="INSTALLING", restore_attempts=3, install_attempts=2
        )
        mock_provider = AsyncMock()
        mock_provider.ready = AsyncMock(return_value=True)
        sm._bridge_mount_provider = mock_provider
        await sm.activate()
        sm._patch_object.assert_any_call(
            {"status": {"restoreAttempts": 0, "installAttempts": 0}}
        )
        self.assertEqual(sm.current_state.value, "ACTIVE")

    async def test_activate_skips_patch_when_counters_zero(self):
        sm = _create_state_machine(
            state="INSTALLING", restore_attempts=0, install_attempts=0
        )
        mock_provider = AsyncMock()
        mock_provider.ready = AsyncMock(return_value=True)
        sm._bridge_mount_provider = mock_provider
        await sm.activate()
        sm._patch_object.assert_not_called()
        self.assertEqual(sm.current_state.value, "ACTIVE")


class TestFullReconciliationLoop(IsolatedAsyncioTestCase):
    async def test_hpa_mismatch_eventually_errors(self):
        """Simulate the full reconciler loop with a persistent HPA mismatch.
        The mount should reach ERROR and not loop forever."""
        config = OperatorConfiguration()
        max_attempts = config.BRIDGE_MOUNT_MAX_RESTORE_ATTEMPTS

        data = _make_bridge_mount_data(state="ACTIVE", restore_attempts=0, install_attempts=0)

        for cycle in range(max_attempts * 3):  # generous upper bound
            with patch("gefyra.base.k8s"):
                model = GefyraBridgeMountObject(data)
            sm = GefyraBridgeMount(
                model=model,
                configuration=config,
                logger=logger,
                initial=data["state"],
            )
            sm._patch_object = AsyncMock()
            sm.post_event = AsyncMock()
            mock_provider = AsyncMock()
            mock_provider.prepare = AsyncMock()
            mock_provider.prepared = AsyncMock(return_value=True)
            mock_provider.install = AsyncMock()
            mock_provider.ready = AsyncMock(return_value=False)  # HPA mismatch
            sm._bridge_mount_provider = mock_provider

            # Mirror reconciler logic from handler/bridge_mounts.py
            if sm.requested.is_active:
                await sm.arrange()
            elif sm.preparing.is_active:
                await sm.install()
            elif sm.installing.is_active:
                await sm.install()
            elif sm.error.is_active:
                break
            elif sm.restoring.is_active:
                await sm.send("restore")
            elif sm.active.is_active:
                await sm.send("restore")

            new_state = sm.current_state.value
            data["state"] = new_state
            for call in sm._patch_object.call_args_list:
                patch_data = call.args[0]
                if "status" in patch_data:
                    data.setdefault("status", {}).update(patch_data["status"])

            if new_state == "ERROR":
                break

        self.assertEqual(data["state"], "ERROR")
