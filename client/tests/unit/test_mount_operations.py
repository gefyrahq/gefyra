from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client import ApiException

from gefyra.exceptions import GefyraMountNotFoundError
from gefyra.local.mount import get_gefyrabridgemount, handle_delete_gefyramount


class TestGetGefyrabridgemount:
    """Tests for get_gefyrabridgemount() — the low-level K8s getter."""

    def test_raises_api_exception_on_404(self):
        """get_gefyrabridgemount must raise ApiException on 404 (not return {})."""
        config = MagicMock()
        config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object.side_effect = (
            ApiException(status=404, reason="Not Found")
        )
        with pytest.raises(ApiException) as exc_info:
            get_gefyrabridgemount(config, "nonexistent-mount")
        assert exc_info.value.status == 404

    def test_raises_api_exception_on_other_errors(self):
        """Non-404 errors are also raised."""
        config = MagicMock()
        config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object.side_effect = (
            ApiException(status=500, reason="Internal Server Error")
        )
        with pytest.raises(ApiException) as exc_info:
            get_gefyrabridgemount(config, "some-mount")
        assert exc_info.value.status == 500

    def test_returns_mount_on_success(self):
        """Successful API call returns the raw mount dict."""
        config = MagicMock()
        expected = {"metadata": {"name": "my-mount"}}
        config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object.return_value = (
            expected
        )
        result = get_gefyrabridgemount(config, "my-mount")
        assert result == expected


class TestHandleDeleteGefyramount:
    """Tests for handle_delete_gefyramount() — the low-level K8s deleter."""

    def test_raises_not_found_on_404(self):
        """Deleting a non-existent mount must raise GefyraMountNotFoundError."""
        config = MagicMock()
        config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object.side_effect = (
            ApiException(status=404, reason="Not Found")
        )
        with pytest.raises(GefyraMountNotFoundError, match="not found"):
            handle_delete_gefyramount(config, "nonexistent", force=False, wait=False)

    def test_returns_true_on_successful_delete_nowait(self):
        """Successful delete without waiting returns True."""
        config = MagicMock()
        config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object.return_value = {}
        result = handle_delete_gefyramount(
            config, "my-mount", force=False, wait=False
        )
        assert result is True

    def test_wait_returns_true_when_object_disappears(self):
        """When waiting, returns True once the object 404s."""
        config = MagicMock()
        config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object.return_value = {}
        # First get call succeeds (still exists), second 404s (gone)
        config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object.side_effect = [
            {"metadata": {"name": "my-mount"}},
            ApiException(status=404, reason="Not Found"),
        ]
        with patch("gefyra.local.mount.time.sleep"):
            result = handle_delete_gefyramount(
                config, "my-mount", force=False, wait=True, timeout=10
            )
        assert result is True

    def test_wait_returns_false_on_timeout(self):
        """When the object never disappears, returns False after timeout."""
        config = MagicMock()
        config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object.return_value = {}
        # Object always found
        config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object.return_value = {
            "metadata": {"name": "my-mount"}
        }
        with patch("gefyra.local.mount.time.sleep"):
            result = handle_delete_gefyramount(
                config, "my-mount", force=False, wait=True, timeout=3
            )
        assert result is False

    def test_timeout_parameter_is_respected(self):
        """The timeout parameter controls how many poll iterations occur."""
        config = MagicMock()
        config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object.return_value = {}
        config.K8S_CUSTOM_OBJECT_API.get_namespaced_custom_object.return_value = {
            "metadata": {"name": "my-mount"}
        }
        with patch("gefyra.local.mount.time.sleep") as mock_sleep:
            handle_delete_gefyramount(
                config, "my-mount", force=False, wait=True, timeout=5
            )
        assert mock_sleep.call_count == 5

    def test_force_removes_finalizers_before_delete(self):
        """With force=True, finalizers are patched out before deletion."""
        config = MagicMock()
        config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object.return_value = {}
        handle_delete_gefyramount(config, "my-mount", force=True, wait=False)
        config.K8S_CUSTOM_OBJECT_API.patch_namespaced_custom_object.assert_called_once()
        config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object.assert_called_once()

    def test_reraises_non_404_api_errors(self):
        """Non-404 API errors are re-raised."""
        config = MagicMock()
        config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object.side_effect = (
            ApiException(status=500, reason="Internal Server Error")
        )
        with pytest.raises(ApiException) as exc_info:
            handle_delete_gefyramount(config, "my-mount", force=False, wait=False)
        assert exc_info.value.status == 500


class TestGetMountApi:
    """Tests for api.get_mount() — the API-level getter."""

    @patch("gefyra.api.mount.ClientConfiguration")
    @patch("gefyra.api.mount.get_gefyrabridgemount")
    def test_raises_runtime_error_on_404(self, mock_get, mock_config):
        """get_mount raises RuntimeError with descriptive message on 404."""
        from gefyra.api.mount import get_mount

        mock_get.side_effect = ApiException(status=404, reason="Not Found")
        with pytest.raises(RuntimeError, match="not found"):
            get_mount("nonexistent-mount")

    @patch("gefyra.api.mount.ClientConfiguration")
    @patch("gefyra.api.mount.get_gefyrabridgemount")
    def test_returns_mount_object_on_success(self, mock_get, mock_config):
        """get_mount returns a GefyraBridgeMount on success."""
        from gefyra.api.mount import get_mount

        mock_get.return_value = {
            "metadata": {
                "name": "my-mount",
                "uid": "abc-123",
                "namespace": "gefyra",
                "labels": {},
            },
            "provider": "carrier2mount",
            "state": "ACTIVE",
            "stateTransitions": {},
            "target": "deploy/nginx",
            "targetContainer": "nginx",
            "targetNamespace": "default",
        }
        result = get_mount("my-mount")
        assert result.name == "my-mount"


class TestDeleteMountApi:
    """Tests for api.delete_mount() — the API-level deleter."""

    @patch("gefyra.api.mount.ClientConfiguration")
    @patch("gefyra.api.mount.handle_delete_gefyramount")
    def test_passes_timeout_through(self, mock_handle, mock_config):
        """delete_mount passes the timeout parameter to handle_delete_gefyramount."""
        from gefyra.api.mount import delete_mount

        mock_handle.return_value = True
        delete_mount("my-mount", timeout=42, wait=True)
        _, kwargs = mock_handle.call_args
        assert kwargs["timeout"] == 42

    @patch("gefyra.api.mount.ClientConfiguration")
    @patch("gefyra.api.mount.handle_delete_gefyramount")
    def test_propagates_not_found_error(self, mock_handle, mock_config):
        """delete_mount propagates GefyraMountNotFoundError from the handler."""
        from gefyra.api.mount import delete_mount

        mock_handle.side_effect = GefyraMountNotFoundError("not found")
        with pytest.raises(GefyraMountNotFoundError):
            delete_mount("nonexistent")
