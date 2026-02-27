from unittest.mock import MagicMock, patch
import pytest

from gefyra.api.rm import rm, rm_all, _get_bridges_for_container


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.NETWORK_NAME = "gefyra"
    config.CLIENT_ID = "default"
    config.NAMESPACE = "gefyra"
    return config


@pytest.fixture
def mock_container():
    container = MagicMock()
    container.name = "myapp"
    container.attrs = {
        "NetworkSettings": {"Networks": {"gefyra": {"IPAddress": "192.168.99.5"}}}
    }
    return container


@pytest.fixture
def sample_bridges():
    return [
        {
            "metadata": {"name": "myapp-to-default.deploy.nginx", "uid": "uid-1"},
            "client": "default",
            "destinationIP": "192.168.99.5",
            "portMappings": ["80:80"],
            "targetContainer": "nginx",
            "targetNamespace": "default",
            "targetPod": "nginx-abc123",
            "provider": "carrier",
            "state": "ACTIVE",
        },
        {
            "metadata": {"name": "other-to-default.deploy.redis", "uid": "uid-2"},
            "client": "default",
            "destinationIP": "192.168.99.10",
            "portMappings": ["6379:6379"],
            "targetContainer": "redis",
            "targetNamespace": "default",
            "targetPod": "redis-xyz789",
            "provider": "carrier",
            "state": "ACTIVE",
        },
    ]


def test_get_bridges_for_container(mock_config, sample_bridges):
    with patch(
        "gefyra.local.bridge.get_all_gefyrabridges", return_value=sample_bridges
    ):
        result = _get_bridges_for_container(mock_config, "192.168.99.5")
        assert len(result) == 1
        assert result[0]["metadata"]["name"] == "myapp-to-default.deploy.nginx"


def test_get_bridges_for_container_no_match(mock_config, sample_bridges):
    with patch(
        "gefyra.local.bridge.get_all_gefyrabridges", return_value=sample_bridges
    ):
        result = _get_bridges_for_container(mock_config, "192.168.99.99")
        assert len(result) == 0


@patch("gefyra.configuration.ClientConfiguration")
def test_rm_with_bridges(mock_config_cls, mock_container, sample_bridges):
    config = MagicMock()
    config.NETWORK_NAME = "gefyra"
    mock_config_cls.return_value = config
    config.DOCKER.containers.get.return_value = mock_container

    with (
        patch("gefyra.local.bridge.get_all_gefyrabridges", return_value=sample_bridges),
        patch("gefyra.local.bridge.handle_delete_gefyrabridge") as mock_delete,
    ):
        result = rm(name="myapp", connection_name="default", force=True)

    assert result is True
    mock_delete.assert_called_once_with(config, "myapp-to-default.deploy.nginx")
    mock_container.remove.assert_called_once_with(force=True)


@patch("gefyra.configuration.ClientConfiguration")
def test_rm_no_bridges(mock_config_cls, mock_container):
    config = MagicMock()
    config.NETWORK_NAME = "gefyra"
    mock_config_cls.return_value = config
    config.DOCKER.containers.get.return_value = mock_container

    with (
        patch("gefyra.local.bridge.get_all_gefyrabridges", return_value=[]),
        patch("gefyra.local.bridge.handle_delete_gefyrabridge") as mock_delete,
    ):
        result = rm(name="myapp", connection_name="default", force=True)

    assert result is True
    mock_delete.assert_not_called()
    mock_container.remove.assert_called_once_with(force=True)


@patch("gefyra.configuration.ClientConfiguration")
def test_rm_container_not_found(mock_config_cls):
    from docker.errors import NotFound

    config = MagicMock()
    mock_config_cls.return_value = config
    config.DOCKER.containers.get.side_effect = NotFound("not found")

    with pytest.raises(RuntimeError, match="Could not find container 'ghost'"):
        rm(name="ghost", connection_name="default")


@patch("gefyra.configuration.ClientConfiguration")
def test_rm_container_not_in_network(mock_config_cls):
    config = MagicMock()
    config.NETWORK_NAME = "gefyra"
    mock_config_cls.return_value = config

    container = MagicMock()
    container.name = "myapp"
    container.attrs = {"NetworkSettings": {"Networks": {}}}
    config.DOCKER.containers.get.return_value = container

    with (
        patch("gefyra.local.bridge.get_all_gefyrabridges", return_value=[]),
        patch("gefyra.local.bridge.handle_delete_gefyrabridge") as mock_delete,
    ):
        result = rm(name="myapp", connection_name="default", force=True)

    assert result is True
    mock_delete.assert_not_called()
    container.remove.assert_called_once_with(force=True)


@patch("gefyra.configuration.ClientConfiguration")
@patch("gefyra.local.bridge.get_all_containers")
def test_rm_all(mock_get_containers, mock_config_cls):
    from gefyra.types import GefyraLocalContainer

    config = MagicMock()
    config.NETWORK_NAME = "gefyra"
    mock_config_cls.return_value = config

    container1 = MagicMock()
    container1.name = "app1"
    container1.attrs = {
        "NetworkSettings": {"Networks": {"gefyra": {"IPAddress": "192.168.99.5"}}}
    }
    container2 = MagicMock()
    container2.name = "app2"
    container2.attrs = {
        "NetworkSettings": {"Networks": {"gefyra": {"IPAddress": "192.168.99.6"}}}
    }
    config.DOCKER.containers.get.side_effect = [
        container1,
        container2,
        container1,
        container2,
    ]

    mock_get_containers.return_value = [
        GefyraLocalContainer(
            id="abc123",
            short_id="abc",
            name="app1",
            address="192.168.99.5",
            namespace="default",
        ),
        GefyraLocalContainer(
            id="def456",
            short_id="def",
            name="app2",
            address="192.168.99.6",
            namespace="default",
        ),
    ]

    bridges = [
        {
            "metadata": {"name": "bridge-app1", "uid": "uid-1"},
            "destinationIP": "192.168.99.5",
        },
        {
            "metadata": {"name": "bridge-app2", "uid": "uid-2"},
            "destinationIP": "192.168.99.6",
        },
    ]

    with (
        patch("gefyra.local.bridge.get_all_gefyrabridges", return_value=bridges),
        patch("gefyra.local.bridge.handle_delete_gefyrabridge") as mock_delete,
    ):
        result = rm_all(connection_name="default", force=True)

    assert result is True
    assert mock_delete.call_count == 2
    mock_delete.assert_any_call(config, "bridge-app1")
    mock_delete.assert_any_call(config, "bridge-app2")
    container1.remove.assert_called_once_with(force=True)
    container2.remove.assert_called_once_with(force=True)


@patch("gefyra.configuration.ClientConfiguration")
@patch("gefyra.local.bridge.get_all_containers")
@patch("gefyra.api.rm.cleanup_stale_bridges")
def test_rm_all_no_containers(mock_cleanup, mock_get_containers, mock_config_cls):
    config = MagicMock()
    mock_config_cls.return_value = config
    mock_get_containers.return_value = []

    result = rm_all(connection_name="default")

    assert result is True
    mock_cleanup.assert_called_once_with(config=config)


@patch("gefyra.configuration.ClientConfiguration")
def test_rm_with_wait(mock_config_cls, mock_container, sample_bridges):
    config = MagicMock()
    config.NETWORK_NAME = "gefyra"
    mock_config_cls.return_value = config
    config.DOCKER.containers.get.return_value = mock_container

    with (
        patch("gefyra.local.bridge.get_all_gefyrabridges", return_value=sample_bridges),
        patch("gefyra.local.bridge.handle_delete_gefyrabridge"),
        patch("gefyra.api.bridge.wait_for_deletion") as mock_wait,
    ):
        result = rm(name="myapp", connection_name="default", wait=True, force=True)

    assert result is True
    mock_wait.assert_called_once()
    bridges_arg = mock_wait.call_args[0][0]
    assert len(bridges_arg) == 1
    assert bridges_arg[0]["metadata"]["name"] == "myapp-to-default.deploy.nginx"


# --- cleanup_stale_bridges tests ---


@patch("gefyra.configuration.ClientConfiguration")
def test_cleanup_stale_bridges_removes_orphans(mock_config_cls):
    from gefyra.api.rm import cleanup_stale_bridges
    from gefyra.types import GefyraLocalContainer

    config = MagicMock()
    config.NETWORK_NAME = "gefyra"
    mock_config_cls.return_value = config

    live_containers = [
        GefyraLocalContainer(
            id="a1",
            short_id="a1",
            name="alive",
            address="192.168.99.5",
            namespace="default",
        ),
    ]
    bridges = [
        {"metadata": {"name": "alive-bridge"}, "destinationIP": "192.168.99.5"},
        {"metadata": {"name": "dead-bridge"}, "destinationIP": "192.168.99.99"},
    ]

    with (
        patch("gefyra.local.bridge.get_all_containers", return_value=live_containers),
        patch("gefyra.local.bridge.get_all_gefyrabridges", return_value=bridges),
        patch("gefyra.local.bridge.handle_delete_gefyrabridge") as mock_delete,
    ):
        result = cleanup_stale_bridges(connection_name="default")

    assert result == 1
    mock_delete.assert_called_once_with(config, "dead-bridge")


@patch("gefyra.configuration.ClientConfiguration")
def test_cleanup_stale_bridges_nothing_stale(mock_config_cls):
    from gefyra.api.rm import cleanup_stale_bridges
    from gefyra.types import GefyraLocalContainer

    config = MagicMock()
    config.NETWORK_NAME = "gefyra"
    mock_config_cls.return_value = config

    live_containers = [
        GefyraLocalContainer(
            id="a1",
            short_id="a1",
            name="alive",
            address="192.168.99.5",
            namespace="default",
        ),
    ]
    bridges = [
        {"metadata": {"name": "alive-bridge"}, "destinationIP": "192.168.99.5"},
    ]

    with (
        patch("gefyra.local.bridge.get_all_containers", return_value=live_containers),
        patch("gefyra.local.bridge.get_all_gefyrabridges", return_value=bridges),
        patch("gefyra.local.bridge.handle_delete_gefyrabridge") as mock_delete,
    ):
        result = cleanup_stale_bridges(connection_name="default")

    assert result == 0
    mock_delete.assert_not_called()


def test_cleanup_stale_bridges_no_connection():
    from gefyra.api.rm import cleanup_stale_bridges

    with patch(
        "gefyra.configuration.ClientConfiguration", side_effect=Exception("no conn")
    ):
        result = cleanup_stale_bridges(connection_name="default")

    assert result == 0


def test_cleanup_stale_bridges_with_config():
    """When a config is passed directly, it should be reused instead of creating a new one."""
    from gefyra.api.rm import cleanup_stale_bridges
    from gefyra.types import GefyraLocalContainer

    config = MagicMock()
    config.NETWORK_NAME = "gefyra"

    live_containers = [
        GefyraLocalContainer(
            id="a1",
            short_id="a1",
            name="alive",
            address="192.168.99.5",
            namespace="default",
        ),
    ]
    bridges = [
        {"metadata": {"name": "alive-bridge"}, "destinationIP": "192.168.99.5"},
        {"metadata": {"name": "dead-bridge"}, "destinationIP": "192.168.99.99"},
    ]

    with (
        patch("gefyra.local.bridge.get_all_containers", return_value=live_containers),
        patch("gefyra.local.bridge.get_all_gefyrabridges", return_value=bridges),
        patch("gefyra.local.bridge.handle_delete_gefyrabridge") as mock_delete,
        patch("gefyra.configuration.ClientConfiguration") as mock_config_cls,
    ):
        result = cleanup_stale_bridges(config=config)

    assert result == 1
    mock_delete.assert_called_once_with(config, "dead-bridge")
    mock_config_cls.assert_not_called()
