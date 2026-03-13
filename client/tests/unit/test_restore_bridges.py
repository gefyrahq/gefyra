from unittest.mock import MagicMock, patch, call
import pytest

from gefyra.api.run import _restore_bridges_for_container


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.NETWORK_NAME = "gefyra"
    config.NAMESPACE = "gefyra"
    config.CLIENT_ID = "default"
    return config


@pytest.fixture
def mock_container():
    container = MagicMock()
    container.name = "myapp"
    container.attrs = {
        "NetworkSettings": {
            "Networks": {"gefyra": {"IPAddress": "192.168.99.20"}}
        }
    }
    return container


@pytest.fixture
def sample_bridges():
    return {
        "items": [
            {
                "metadata": {
                    "name": "bridge-1",
                    "labels": {"gefyra.dev/client-container": "myapp"},
                },
                "destinationIP": "192.168.99.5",
                "state": "ACTIVE",
            },
            {
                "metadata": {
                    "name": "bridge-2",
                    "labels": {"gefyra.dev/client-container": "myapp"},
                },
                "destinationIP": "192.168.99.5",
                "state": "ACTIVE",
            },
        ]
    }


def test_restore_bridges_patches_destination_ip(
    mock_config, mock_container, sample_bridges
):
    mock_config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object.return_value = (
        sample_bridges
    )

    _restore_bridges_for_container(mock_config, mock_container)

    mock_config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object.assert_called_once_with(
        group="gefyra.dev",
        version="v1",
        namespace="gefyra",
        plural="gefyrabridges",
        label_selector="gefyra.dev/client-container=myapp",
    )
    assert (
        mock_config.K8S_CUSTOM_OBJECT_API.patch_namespaced_custom_object.call_count == 2
    )
    mock_config.K8S_CUSTOM_OBJECT_API.patch_namespaced_custom_object.assert_any_call(
        group="gefyra.dev",
        version="v1",
        namespace="gefyra",
        plural="gefyrabridges",
        name="bridge-1",
        body={"destinationIP": "192.168.99.20"},
    )
    mock_config.K8S_CUSTOM_OBJECT_API.patch_namespaced_custom_object.assert_any_call(
        group="gefyra.dev",
        version="v1",
        namespace="gefyra",
        plural="gefyrabridges",
        name="bridge-2",
        body={"destinationIP": "192.168.99.20"},
    )


def test_restore_bridges_skips_when_ip_unchanged(mock_config, mock_container):
    """Bridge already has the same IP — no patch should be issued."""
    mock_config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object.return_value = {
        "items": [
            {
                "metadata": {
                    "name": "bridge-1",
                    "labels": {"gefyra.dev/client-container": "myapp"},
                },
                "destinationIP": "192.168.99.20",  # same as new container IP
                "state": "ACTIVE",
            }
        ]
    }

    _restore_bridges_for_container(mock_config, mock_container)

    mock_config.K8S_CUSTOM_OBJECT_API.patch_namespaced_custom_object.assert_not_called()


def test_restore_bridges_no_matching_bridges(mock_config, mock_container):
    """No bridges match the container name — nothing happens."""
    mock_config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object.return_value = {
        "items": []
    }

    _restore_bridges_for_container(mock_config, mock_container)

    mock_config.K8S_CUSTOM_OBJECT_API.patch_namespaced_custom_object.assert_not_called()


def test_restore_bridges_handles_network_missing(mock_config):
    """Container not on the Gefyra network — should return gracefully."""
    container = MagicMock()
    container.name = "myapp"
    container.attrs = {"NetworkSettings": {"Networks": {}}}

    _restore_bridges_for_container(mock_config, container)

    mock_config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object.assert_not_called()


def test_restore_bridges_handles_api_error_on_list(mock_config, mock_container):
    """K8s API error when listing bridges — should not raise."""
    from kubernetes.client import ApiException

    mock_config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object.side_effect = (
        ApiException(status=500, reason="Internal Server Error")
    )

    _restore_bridges_for_container(mock_config, mock_container)

    mock_config.K8S_CUSTOM_OBJECT_API.patch_namespaced_custom_object.assert_not_called()


def test_restore_bridges_handles_api_error_on_patch(
    mock_config, mock_container, sample_bridges
):
    """K8s API error when patching a bridge — should continue to next bridge."""
    from kubernetes.client import ApiException

    mock_config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object.return_value = (
        sample_bridges
    )
    mock_config.K8S_CUSTOM_OBJECT_API.patch_namespaced_custom_object.side_effect = [
        ApiException(status=422, reason="Unprocessable Entity"),
        None,  # second patch succeeds
    ]

    _restore_bridges_for_container(mock_config, mock_container)

    # Both patches were attempted despite first one failing
    assert (
        mock_config.K8S_CUSTOM_OBJECT_API.patch_namespaced_custom_object.call_count == 2
    )
