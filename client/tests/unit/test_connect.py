import pytest
from unittest.mock import patch, MagicMock, mock_open
import socket

from gefyra.api.connect import connect, disconnect, list_connections, remove_connection
from gefyra.exceptions import GefyraConnectionError
from gefyra.types import GefyraClientState


class TestConnect:

    def _setup_existing_connection_mocks(
        self, mock_get_client, mock_config, mock_list_connections
    ):
        """Setup common mocks for existing connection tests."""
        # Mock connection exists
        mock_connection = MagicMock()
        mock_connection.name = "test-connection"
        mock_list_connections.return_value = [mock_connection]

        # Mock configuration
        mock_config_instance = MagicMock()
        mock_config_instance.CONNECTION_TIMEOUT = 60
        mock_config_instance.CARGO_ENDPOINT = "test.example.com:8080"
        mock_config_instance.WIREGUARD_MTU = "1340"
        mock_config.return_value = mock_config_instance
        mock_config_instance.DOCKER.containers.get.return_value = MagicMock()

        # Mock client
        mock_client = MagicMock()
        mock_client.state = GefyraClientState.ACTIVE
        mock_client.provider_config.pendpoint = "test.example.com:8080"
        mock_get_client.return_value = mock_client

        return mock_client, mock_config_instance

    @patch("gefyra.api.connect.list_connections")
    @patch("gefyra.api.connect.ClientConfiguration")
    @patch("gefyra.api.connect.get_client")
    def test_connect_existing_connection(
        self, mock_get_client, mock_config, mock_list_connections
    ):
        # Setup mocks
        _, _ = self._setup_existing_connection_mocks(
            mock_get_client, mock_config, mock_list_connections
        )

        with patch("gefyra.api.connect.get_or_create_gefyra_network") as mock_network:
            mock_network.return_value.attrs = {
                "IPAM": {"Config": [{"Subnet": "192.168.1.0/24"}]}
            }

            with patch("socket.gethostbyname_ex"), patch(
                "gefyra.api.connect.create_wireguard_config",
                return_value="wireguard config",
            ), patch("builtins.open", mock_open()), patch(
                "gefyra.api.connect.get_cargo_ip_from_netaddress",
                return_value="192.168.1.100",
            ), patch(
                "gefyra.api.connect.handle_docker_get_or_create_container"
            ), patch(
                "gefyra.api.connect.probe_wireguard_connection"
            ), patch(
                "time.sleep"
            ):

                result = connect("test-connection", None)

                assert result is True
                mock_get_client.assert_called_once()

    @patch("gefyra.api.connect.list_connections")
    @patch("gefyra.api.connect.GefyraClientConfig")
    @patch("gefyra.api.connect.ClientConfiguration")
    @patch("gefyra.api.connect.compose_kubeconfig_for_serviceaccount")
    @patch("gefyra.api.connect.get_gefyra_config_location")
    def test_connect_new_connection(
        self,
        mock_config_location,
        mock_compose_kubeconfig,
        mock_client_config,
        mock_gclient_config,
        mock_list_connections,
    ):
        # Setup for new connection
        mock_list_connections.return_value = []
        mock_config_location.return_value = "/tmp/gefyra"
        mock_compose_kubeconfig.return_value = "kubeconfig content"

        # Setup client config file
        mock_client_config_file = MagicMock()
        mock_client_config_file.read.return_value = """{
        "client_id": "test-client",
        "token": "dGVzdA==",
        "kubernetes_server": "https://k8s.example.com",
        "ca_crt": "ca-cert",
        "gefyra_server": "gefyra.example.com:8080"}"""

        # Setup GefyraClientConfig
        mock_gclient_conf = MagicMock()
        mock_gclient_conf.client_id = "test-client"
        mock_gclient_conf.token = "dGVzdA=="
        mock_gclient_conf.kubernetes_server = "https://k8s.example.com"
        mock_gclient_conf.ca_crt = "ca-cert"
        mock_gclient_conf.gefyra_server = "gefyra.example.com:8080"
        mock_gclient_conf.wireguard_mtu = None
        mock_gclient_config.from_json_str.return_value = mock_gclient_conf

        # Setup ClientConfiguration
        mock_config_instance = MagicMock()
        mock_config_instance.CONNECTION_TIMEOUT = 60
        mock_config_instance.CARGO_PROBE_TIMEOUT = 60
        mock_config_instance.CARGO_ENDPOINT = None
        mock_config_instance.WIREGUARD_MTU = "1340"
        mock_client_config.return_value = mock_config_instance

        with patch(
            "gefyra.api.connect.handle_get_gefyraclient"
        ) as mock_get_gefyraclient:
            mock_gefyra_client = MagicMock()
            mock_get_gefyraclient.return_value = mock_gefyra_client

            with patch("gefyra.api.connect.GefyraClient") as mock_client_class:
                # Setup client and network
                mock_client = MagicMock()
                mock_client.state = GefyraClientState.ACTIVE
                mock_client.provider_config.pendpoint = "gefyra.example.com:8080"
                mock_client_class.return_value = mock_client

                with patch(
                    "gefyra.api.connect.get_or_create_gefyra_network"
                ) as mock_network:
                    mock_network.return_value.attrs = {
                        "IPAM": {"Config": [{"Subnet": "192.168.1.0/24"}]}
                    }

                    with patch("socket.gethostbyname_ex"), patch(
                        "gefyra.api.connect.create_wireguard_config",
                        return_value="wireguard config",
                    ), patch("builtins.open", mock_open()), patch(
                        "gefyra.api.connect.get_cargo_ip_from_netaddress",
                        return_value="192.168.1.100",
                    ), patch(
                        "gefyra.api.connect.handle_docker_get_or_create_container"
                    ), patch(
                        "gefyra.api.connect.probe_wireguard_connection"
                    ), patch(
                        "time.sleep"
                    ):

                        result = connect("test-connection", mock_client_config_file)

                        assert result is True
                        mock_client_config_file.read.assert_called_once()
                        mock_client_config_file.close.assert_called_once()

    @patch("gefyra.api.connect.list_connections")
    def test_connect_no_client_config_new_connection(self, mock_list_connections):
        mock_list_connections.return_value = []

        with pytest.raises(GefyraConnectionError) as exc_info:
            connect("test-connection", None)

        assert (
            "Connection is not yet created and no client configuration has been provided"
            in str(exc_info.value)
        )

    @patch("gefyra.api.connect.list_connections")
    @patch("gefyra.api.connect.ClientConfiguration")
    @patch("gefyra.api.connect.get_client")
    def test_connect_api_exception_retry(
        self, mock_get_client, mock_config, mock_list_connections
    ):
        import kubernetes

        # Setup mocks
        mock_client, _ = self._setup_existing_connection_mocks(
            mock_get_client, mock_config, mock_list_connections
        )

        # Mock ApiException with status 500 on first call, success on second
        api_exception = kubernetes.client.exceptions.ApiException(status=500)
        mock_client.activate_connection.side_effect = [api_exception, None]

        with patch("gefyra.api.connect.get_or_create_gefyra_network") as mock_network:
            mock_network_instance = MagicMock()
            mock_network_instance.attrs = {
                "IPAM": {"Config": [{"Subnet": "192.168.1.0/24"}]}
            }
            mock_network.return_value = mock_network_instance

            with patch("socket.gethostbyname_ex"), patch(
                "gefyra.api.connect.create_wireguard_config",
                return_value="wireguard config",
            ), patch("builtins.open", mock_open()), patch(
                "gefyra.api.connect.get_cargo_ip_from_netaddress",
                return_value="192.168.1.100",
            ), patch(
                "gefyra.api.connect.handle_docker_get_or_create_container"
            ), patch(
                "gefyra.api.connect.probe_wireguard_connection"
            ), patch(
                "time.sleep"
            ):

                result = connect("test-connection", None)

                assert result is True
                assert mock_client.activate_connection.call_count == 2
                mock_network_instance.remove.assert_called_once()

    @patch("gefyra.api.connect.list_connections")
    @patch("gefyra.api.connect.ClientConfiguration")
    @patch("gefyra.api.connect.get_client")
    def test_connect_socket_error_timeout(
        self, mock_get_client, mock_config, mock_list_connections
    ):
        # Setup mocks
        _, mock_config_instance = self._setup_existing_connection_mocks(
            mock_get_client, mock_config, mock_list_connections
        )
        mock_config_instance.CONNECTION_TIMEOUT = 2

        with patch("gefyra.api.connect.get_or_create_gefyra_network") as mock_network:
            mock_network_instance = MagicMock()
            mock_network_instance.attrs = {
                "IPAM": {"Config": [{"Subnet": "192.168.1.0/24"}]}
            }
            mock_network.return_value = mock_network_instance

            with patch(
                "gefyra.api.connect.create_wireguard_config",
                return_value="wireguard config",
            ), patch("builtins.open", mock_open()), patch(
                "socket.gethostbyname_ex",
                side_effect=socket.gaierror("Name resolution failed"),
            ), patch(
                "time.sleep"
            ):

                with pytest.raises(GefyraConnectionError) as exc_info:
                    connect("test-connection", None)

                assert "Cannot resolve host 'test.example.com'" in str(exc_info.value)


class TestDisconnect:

    @patch("gefyra.api.connect.get_or_create_gefyra_network")
    @patch("gefyra.api.connect.ClientConfiguration")
    @patch("gefyra.api.connect.get_client")
    def test_disconnect_success(self, mock_get_client, mock_config, mock_network):
        # Setup mocks
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance

        mock_cargo_container = MagicMock()
        mock_config_instance.DOCKER.containers.get.return_value = mock_cargo_container

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Execute test
        result = disconnect("test-connection")

        # Assertions
        assert result is True
        mock_cargo_container.stop.assert_called_once()
        mock_client.deactivate_connection.assert_called_once()

    @patch("gefyra.api.connect.get_or_create_gefyra_network")
    @patch("gefyra.api.connect.ClientConfiguration")
    @patch("gefyra.api.connect.get_client")
    def test_disconnect_container_not_found(
        self, mock_get_client, mock_config, mock_network
    ):
        import docker

        # Setup mocks
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance
        mock_config_instance.DOCKER.containers.get.side_effect = docker.errors.NotFound(
            "Container not found"
        )

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Execute test
        result = disconnect("test-connection")

        # Assertions
        assert result is True
        mock_client.deactivate_connection.assert_called_once()


class TestListConnections:

    def _create_mock_container(
        self,
        status="running",
        name="gefyra-cargo-test",
        connection_name="test-connection",
        version="1.0.0",
    ):
        """Helper to create mock container with common attributes."""
        mock_container = MagicMock()
        mock_container.status = status
        mock_container.name = name
        mock_container.labels = {
            "connection_name.gefyra.dev": connection_name,
            "version.gefyra.dev": version,
        }
        mock_container.attrs = {"Created": "2023-01-01T00:00:00Z"}
        return mock_container

    @patch("gefyra.api.connect.ClientConfiguration")
    @patch("gefyra.api.connect.probe_wireguard_connection")
    def test_list_connections_running(self, mock_probe, mock_config):
        # Setup mocks
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance

        mock_container = self._create_mock_container()
        mock_config_instance.DOCKER.containers.list.return_value = [mock_container]

        # Execute test
        result = list_connections()

        # Assertions
        assert len(result) == 1
        assert result[0].name == "test-connection"
        assert result[0].version == "1.0.0"
        assert result[0].status == "running"
        mock_probe.assert_called_once()

    @patch("gefyra.api.connect.ClientConfiguration")
    @patch("gefyra.api.connect.probe_wireguard_connection")
    def test_list_connections_error_state(self, mock_probe, mock_config):
        # Setup mocks
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance

        mock_container = self._create_mock_container()
        mock_config_instance.DOCKER.containers.list.return_value = [mock_container]
        mock_probe.side_effect = GefyraConnectionError("Connection failed")

        # Execute test
        result = list_connections()

        # Assertions
        assert len(result) == 1
        assert result[0].status == "error"

    @patch("gefyra.api.connect.ClientConfiguration")
    def test_list_connections_stopped(self, mock_config):
        # Setup mocks
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance

        mock_container = self._create_mock_container(status="stopped")
        mock_config_instance.DOCKER.containers.list.return_value = [mock_container]

        # Execute test
        result = list_connections()

        # Assertions
        assert len(result) == 1
        assert result[0].status == "stopped"


class TestRemoveConnection:

    @patch("gefyra.api.connect.handle_remove_network")
    @patch("gefyra.api.connect.ClientConfiguration")
    @patch("gefyra.api.connect.get_client")
    @patch("gefyra.api.connect.get_gefyra_config_location")
    @patch("os.remove")
    def test_remove_connection_success(
        self,
        mock_os_remove,
        mock_config_location,
        mock_get_client,
        mock_config,
        mock_handle_remove_network,
    ):
        # Setup mocks
        mock_config_location.return_value = "/tmp/gefyra"

        mock_config_instance = MagicMock()
        mock_config_instance.CONNECTION_NAME = "test-connection"
        mock_config.return_value = mock_config_instance

        mock_cargo_container = MagicMock()
        mock_config_instance.DOCKER.containers.get.return_value = mock_cargo_container

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Execute test
        remove_connection("test-connection")

        # Assertions
        mock_client.deactivate_connection.assert_called_once()
        mock_cargo_container.remove.assert_called_once_with(force=True)
        mock_handle_remove_network.assert_called_once()
        assert mock_os_remove.call_count == 2

    @patch("gefyra.api.connect.handle_remove_network")
    @patch("gefyra.api.connect.ClientConfiguration")
    @patch("gefyra.api.connect.get_client")
    @patch("gefyra.api.connect.get_gefyra_config_location")
    @patch("os.remove")
    def test_remove_connection_with_exceptions(
        self,
        mock_os_remove,
        mock_config_location,
        mock_get_client,
        mock_config,
        mock_handle_remove_network,
    ):
        import docker

        # Setup mocks with exceptions
        mock_config_location.return_value = "/tmp/gefyra"

        mock_config_instance = MagicMock()
        mock_config_instance.CONNECTION_NAME = "test-connection"
        mock_config.return_value = mock_config_instance
        mock_config_instance.DOCKER.containers.get.side_effect = docker.errors.NotFound(
            "Container not found"
        )

        mock_client = MagicMock()
        mock_client.deactivate_connection.side_effect = Exception("Deactivation failed")
        mock_get_client.return_value = mock_client

        mock_os_remove.side_effect = OSError("File not found")

        # Execute test - should not raise exception despite internal errors
        remove_connection("test-connection")

        # Assertions
        mock_handle_remove_network.assert_called_once()
        assert mock_os_remove.call_count == 2
