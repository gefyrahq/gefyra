import unittest
from unittest.mock import Mock, MagicMock, patch
import kubernetes.client.exceptions
import urllib3.exceptions
import click

from gefyra.cli.connections import _manage_container_and_bridges


class TestManageContainerAndBridges(unittest.TestCase):
    """Tests for _manage_container_and_bridges function"""

    def setUp(self):
        """Set up test fixtures"""
        self.connection_name = "test-connection"
        self.update_callback = Mock()

    @patch("gefyra.cli.connections.console")
    @patch("gefyra.api.delete_bridge")
    @patch("gefyra.api.list_containers")
    @patch("gefyra.api.list_bridges")
    def test_no_bridges_no_containers(
        self, mock_list_bridges, mock_list_containers, mock_delete_bridge, mock_console
    ):
        """Test when there are no bridges or containers"""
        mock_list_bridges.return_value = []
        mock_list_containers.return_value = [("test-connection", [])]

        _manage_container_and_bridges(
            self.connection_name, force=True, update_callback=self.update_callback
        )

        mock_list_bridges.assert_called_once_with(connection_name=self.connection_name)
        mock_list_containers.assert_called_once_with(self.connection_name)
        mock_delete_bridge.assert_not_called()

    @patch("gefyra.cli.connections.console")
    @patch("gefyra.api.delete_bridge")
    @patch("gefyra.api.list_containers")
    @patch("gefyra.api.list_bridges")
    def test_remove_single_bridge_with_force(
        self, mock_list_bridges, mock_list_containers, mock_delete_bridge, mock_console
    ):
        """Test removing a single bridge with force=True"""
        bridge_mock = Mock()
        bridge_mock.name = "test-bridge"
        container_mock = Mock()
        mock_list_bridges.return_value = [(container_mock, bridge_mock)]
        mock_list_containers.return_value = [("test-connection", [])]

        _manage_container_and_bridges(
            self.connection_name, force=True, update_callback=self.update_callback
        )

        mock_delete_bridge.assert_called_once_with(
            name="test-bridge", connection_name=self.connection_name
        )
        self.update_callback.assert_called_with(
            "Removing GefyraBridge 'test-bridge'..."
        )

    @patch("gefyra.cli.connections.console")
    @patch("gefyra.api.delete_bridge")
    @patch("gefyra.api.list_containers")
    @patch("gefyra.api.list_bridges")
    def test_remove_multiple_bridges_with_force(
        self, mock_list_bridges, mock_list_containers, mock_delete_bridge, mock_console
    ):
        """Test removing multiple bridges with force=True"""
        bridge_mock1 = Mock()
        bridge_mock1.name = "test-bridge-1"
        bridge_mock2 = Mock()
        bridge_mock2.name = "test-bridge-2"
        container_mock = Mock()
        mock_list_bridges.return_value = [
            (container_mock, bridge_mock1),
            (container_mock, bridge_mock2),
        ]
        mock_list_containers.return_value = [("test-connection", [])]

        _manage_container_and_bridges(
            self.connection_name, force=True, update_callback=self.update_callback
        )

        assert mock_delete_bridge.call_count == 2
        mock_delete_bridge.assert_any_call(
            name="test-bridge-1", connection_name=self.connection_name
        )
        mock_delete_bridge.assert_any_call(
            name="test-bridge-2", connection_name=self.connection_name
        )

    @patch("gefyra.cli.connections.console")
    @patch("gefyra.cli.connections.click.confirm")
    @patch("gefyra.api.delete_bridge")
    @patch("gefyra.api.list_containers")
    @patch("gefyra.api.list_bridges")
    def test_remove_bridge_with_user_confirmation(
        self,
        mock_list_bridges,
        mock_list_containers,
        mock_delete_bridge,
        mock_confirm,
        mock_console,
    ):
        """Test removing bridge with user confirmation"""
        bridge_mock = Mock()
        bridge_mock.name = "test-bridge"
        container_mock = Mock()
        mock_list_bridges.return_value = [(container_mock, bridge_mock)]
        mock_list_containers.return_value = [("test-connection", [])]
        mock_confirm.return_value = True

        _manage_container_and_bridges(
            self.connection_name, force=False, update_callback=self.update_callback
        )

        mock_confirm.assert_called_with("Do you want to remove them?", abort=True)
        mock_delete_bridge.assert_called_once()

    @patch("gefyra.cli.connections.console")
    @patch("gefyra.cli.connections.click.confirm")
    @patch("gefyra.api.delete_bridge")
    @patch("gefyra.api.list_containers")
    @patch("gefyra.api.list_bridges")
    def test_skip_bridge_removal_user_confirms_no(
        self,
        mock_list_bridges,
        mock_list_containers,
        mock_delete_bridge,
        mock_confirm,
        mock_console,
    ):
        """Test skipping bridge removal when user does not confirm"""
        bridge_mock = Mock()
        bridge_mock.name = "test-bridge"
        container_mock = Mock()
        mock_list_bridges.return_value = [(container_mock, bridge_mock)]
        mock_list_containers.return_value = [("test-connection", [])]
        mock_confirm.side_effect = click.Abort()

        with self.assertRaises(click.Abort):
            _manage_container_and_bridges(
                self.connection_name, force=False, update_callback=self.update_callback
            )

        mock_delete_bridge.assert_not_called()

    @patch("gefyra.api.list_containers")
    @patch("gefyra.api.list_bridges")
    def test_bridges_list_max_retry_error(
        self, mock_list_bridges, mock_list_containers
    ):
        """Test handling of MaxRetryError when listing bridges"""
        error = urllib3.exceptions.MaxRetryError(pool=Mock(), url="http://test")
        mock_list_bridges.side_effect = error
        mock_list_containers.return_value = [("test-connection", [])]

        # Should not raise and continue to container listing
        _manage_container_and_bridges(
            self.connection_name, force=True, update_callback=self.update_callback
        )

        mock_list_bridges.assert_called_once()
        mock_list_containers.assert_called_once()

    @patch("gefyra.api.list_containers")
    @patch("gefyra.api.list_bridges")
    def test_bridges_list_api_exception(self, mock_list_bridges, mock_list_containers):
        """Test handling of ApiException when listing bridges"""
        error = kubernetes.client.exceptions.ApiException(status=500)
        mock_list_bridges.side_effect = error
        mock_list_containers.return_value = [("test-connection", [])]

        # Should not raise and continue to container listing
        _manage_container_and_bridges(
            self.connection_name, force=True, update_callback=self.update_callback
        )

        mock_list_bridges.assert_called_once()
        mock_list_containers.assert_called_once()

    @patch("gefyra.cli.connections.console")
    @patch("gefyra.configuration.ClientConfiguration")
    @patch("gefyra.api.list_containers")
    @patch("gefyra.api.list_bridges")
    def test_remove_single_container_with_force(
        self, mock_list_bridges, mock_list_containers, mock_client_config, mock_console
    ):
        """Test removing a single container with force=True"""
        # Mock bridges
        mock_list_bridges.return_value = []

        # Mock containers
        gefyra_container = Mock()
        gefyra_container.name = "test-cargo"
        mock_list_containers.return_value = [("test-connection", [gefyra_container])]

        # Mock ClientConfiguration and DOCKER
        config_instance = MagicMock()
        docker_container = Mock()
        config_instance.DOCKER.containers.get.return_value = docker_container
        mock_client_config.return_value = config_instance

        _manage_container_and_bridges(
            self.connection_name, force=True, update_callback=self.update_callback
        )

        mock_client_config.assert_called_once_with(connection_name=self.connection_name)
        config_instance.DOCKER.containers.get.assert_called_once_with("test-cargo")
        docker_container.remove.assert_called_once_with(force=True)
        self.update_callback.assert_called_with("Removing Gefyra cargo 'test-cargo'...")

    @patch("gefyra.cli.connections.console")
    @patch("gefyra.configuration.ClientConfiguration")
    @patch("gefyra.api.list_containers")
    @patch("gefyra.api.list_bridges")
    def test_remove_multiple_containers_with_force(
        self, mock_list_bridges, mock_list_containers, mock_client_config, mock_console
    ):
        """Test removing multiple containers with force=True"""
        mock_list_bridges.return_value = []

        gefyra_container1 = Mock()
        gefyra_container1.name = "test-cargo-1"
        gefyra_container2 = Mock()
        gefyra_container2.name = "test-cargo-2"
        mock_list_containers.return_value = [
            ("test-connection", [gefyra_container1, gefyra_container2])
        ]

        config_instance = MagicMock()
        docker_container1 = Mock()
        docker_container2 = Mock()
        config_instance.DOCKER.containers.get.side_effect = [
            docker_container1,
            docker_container2,
        ]
        mock_client_config.return_value = config_instance

        _manage_container_and_bridges(
            self.connection_name, force=True, update_callback=self.update_callback
        )

        assert config_instance.DOCKER.containers.get.call_count == 2
        assert docker_container1.remove.call_count == 1
        assert docker_container2.remove.call_count == 1

    def test_remove_container_without_force_with_user_confirmation(self):
        """Test removing container with user confirmation"""
        with patch("gefyra.cli.connections.console"):
            with patch("gefyra.cli.connections.click.confirm") as mock_confirm:
                with patch("gefyra.api.list_containers") as mock_list_containers:
                    with patch("gefyra.api.list_bridges") as mock_list_bridges:
                        with patch(
                            "gefyra.configuration.ClientConfiguration"
                        ) as mock_client_config:
                            mock_list_bridges.return_value = []

                            gefyra_container = Mock()
                            gefyra_container.name = "test-cargo"
                            mock_list_containers.return_value = [
                                ("test-connection", [gefyra_container])
                            ]

                            config_instance = MagicMock()
                            docker_container = Mock()
                            config_instance.DOCKER.containers.get.return_value = (
                                docker_container
                            )
                            mock_client_config.return_value = config_instance

                            mock_confirm.return_value = True

                            _manage_container_and_bridges(
                                self.connection_name,
                                force=False,
                                update_callback=self.update_callback,
                            )

                            mock_confirm.assert_called_with(
                                "Do you want to remove them?", abort=True
                            )
                            docker_container.remove.assert_called_once_with(force=True)

    @patch("gefyra.cli.connections.console")
    @patch("gefyra.configuration.ClientConfiguration")
    @patch("gefyra.api.list_containers")
    @patch("gefyra.api.list_bridges")
    def test_container_removal_exception_raises(
        self, mock_list_bridges, mock_list_containers, mock_client_config, mock_console
    ):
        """Test that container removal exception is raised (not caught)"""
        mock_list_bridges.return_value = []

        gefyra_container1 = Mock()
        gefyra_container1.name = "test-cargo-1"
        mock_list_containers.return_value = [("test-connection", [gefyra_container1])]

        config_instance = MagicMock()
        docker_container1 = Mock()
        docker_container1.remove.side_effect = Exception("Container removal failed")
        config_instance.DOCKER.containers.get.return_value = docker_container1
        mock_client_config.return_value = config_instance

        # Should raise because function doesn't catch container removal exceptions
        with self.assertRaises(Exception) as context:
            _manage_container_and_bridges(
                self.connection_name, force=True, update_callback=self.update_callback
            )

        self.assertIn("Container removal failed", str(context.exception))

    def test_update_callback_none(self):
        """Test that function works when update_callback is None"""
        with patch("gefyra.api.list_bridges") as mock_list_bridges:
            with patch("gefyra.api.list_containers") as mock_list_containers:
                with patch("gefyra.api.delete_bridge") as mock_delete_bridge:
                    bridge_mock = Mock(name="test-bridge")
                    container_mock = Mock()
                    mock_list_bridges.return_value = [(container_mock, bridge_mock)]
                    mock_list_containers.return_value = [("test-connection", [])]

                    _manage_container_and_bridges(
                        self.connection_name, force=True, update_callback=None
                    )

                    mock_delete_bridge.assert_called_once()

    @patch("gefyra.cli.connections.console")
    @patch("gefyra.api.delete_bridge")
    @patch("gefyra.api.list_containers")
    @patch("gefyra.api.list_bridges")
    def test_bridge_deletion_with_correct_parameters(
        self, mock_list_bridges, mock_list_containers, mock_delete_bridge, mock_console
    ):
        """Test that bridge deletion is called with correct parameters"""
        bridge_mock = Mock()
        bridge_mock.name = "my-bridge"
        container_mock = Mock()
        mock_list_bridges.return_value = [(container_mock, bridge_mock)]
        mock_list_containers.return_value = [("test-connection", [])]

        _manage_container_and_bridges(
            connection_name="my-connection", force=True, update_callback=None
        )

        mock_delete_bridge.assert_called_once_with(
            name="my-bridge", connection_name="my-connection"
        )

    @patch("gefyra.cli.connections.console")
    @patch("gefyra.configuration.ClientConfiguration")
    @patch("gefyra.api.list_containers")
    @patch("gefyra.api.list_bridges")
    def test_client_configuration_connection_name_parameter(
        self, mock_list_bridges, mock_list_containers, mock_client_config, mock_console
    ):
        """Test that ClientConfiguration is called with correct connection_name"""
        mock_list_bridges.return_value = []

        gefyra_container = Mock()
        gefyra_container.name = "test-cargo"
        mock_list_containers.return_value = [("test-connection", [gefyra_container])]

        config_instance = MagicMock()
        docker_container = Mock()
        config_instance.DOCKER.containers.get.return_value = docker_container
        mock_client_config.return_value = config_instance

        _manage_container_and_bridges(
            connection_name="custom-connection", force=True, update_callback=None
        )

        mock_client_config.assert_called_with(connection_name="custom-connection")

    def test_both_bridges_and_containers_removal(self):
        """Test removing both bridges and containers"""
        with patch("gefyra.cli.connections.console"):
            with patch("gefyra.api.list_bridges") as mock_list_bridges:
                with patch("gefyra.api.list_containers") as mock_list_containers:
                    with patch("gefyra.api.delete_bridge") as mock_delete_bridge:
                        with patch(
                            "gefyra.configuration.ClientConfiguration"
                        ) as mock_client_config:
                            bridge_mock = Mock()
                            bridge_mock.name = "test-bridge"
                            container_mock = Mock()
                            gefyra_container = Mock()
                            gefyra_container.name = "test-cargo"

                            mock_list_bridges.return_value = [
                                (container_mock, bridge_mock)
                            ]
                            mock_list_containers.return_value = [
                                ("test-connection", [gefyra_container])
                            ]

                            config_instance = MagicMock()
                            docker_container = Mock()
                            config_instance.DOCKER.containers.get.return_value = (
                                docker_container
                            )
                            mock_client_config.return_value = config_instance

                            _manage_container_and_bridges(
                                self.connection_name,
                                force=True,
                                update_callback=self.update_callback,
                            )

                            mock_delete_bridge.assert_called_once()
                            docker_container.remove.assert_called_once_with(force=True)
