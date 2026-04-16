from unittest.mock import Mock, patch
from kubernetes.client import ApiException

from gefyra.configuration import ClientConfiguration
from gefyra.local.bridge import handle_delete_gefyrabridge


def test_delete_bridge_with_404_error():
    """Test that delete_bridge handles 404 ApiError correctly and logs debug message."""
    config = ClientConfiguration()
    config.NAMESPACE = "test-namespace"
    bridge_name = "test-bridge"

    # Mock the K8S_CUSTOM_OBJECT_API to raise ApiException with status 404
    api_error = ApiException(status=404, reason="Not Found")
    config.K8S_CUSTOM_OBJECT_API = Mock()
    config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object.side_effect = api_error

    # Patch logger to verify debug is called with correct message
    with patch("gefyra.local.bridge.logger") as mock_logger:
        result = handle_delete_gefyrabridge(config, bridge_name)

    # Verify the function returns False
    assert result is False

    # Verify logger.debug was called with the correct message
    expected_message = f"GefyraBridge {bridge_name} not found"
    mock_logger.debug.assert_called_once_with(expected_message)
