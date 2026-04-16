import unittest
from unittest.mock import Mock, MagicMock, patch
import urllib3.exceptions

from gefyra.api.status import _get_client_status, _get_cluster_status, status
from gefyra.local import CARGO_ENDPOINT_LABEL, VERSION_LABEL
from gefyra.types import StatusSummary


class TestGetClientStatus(unittest.TestCase):
    """Tests for _get_client_status function"""

    def setUp(self):
        self.config = MagicMock()
        self.config.CARGO_IMAGE = "gefyra/cargo:latest"
        self.config.KUBE_CONFIG_FILE = "/path/to/kubeconfig"
        self.config.KUBE_CONTEXT = "minikube"
        self.config.CARGO_CONTAINER_NAME = "gefyra-cargo"
        self.config.NETWORK_NAME = "gefyra"

    @patch("gefyra.local.bridge.get_all_gefyrabridges")
    @patch("gefyra.local.cargo.probe_wireguard_connection")
    def test_client_status_all_running(self, mock_probe_wg, mock_get_bridges):
        """Test client status when everything is running"""
        # Mock cargo container
        cargo_container = Mock()
        cargo_container.status = "running"
        cargo_container.attrs = {
            "Config": {
                "Labels": {
                    CARGO_ENDPOINT_LABEL: "192.168.1.1:51820",
                    VERSION_LABEL: "1.0.0",
                }
            }
        }
        cargo_container.image.tags = ["gefyra/cargo:1.0.0"]
        self.config.DOCKER.containers.get.return_value = cargo_container

        # Mock network
        network = Mock()
        network.containers = [Mock(), Mock(), Mock()]  # 3 containers (cargo + 2 others)
        self.config.DOCKER.networks.get.return_value = network

        # Mock bridges
        mock_get_bridges.return_value = [Mock(), Mock()]  # 2 bridges

        result = _get_client_status(self.config)

        self.assertTrue(result.cargo)
        self.assertEqual(result.version, "1.0.0")
        self.assertEqual(result.cargo_image, "gefyra/cargo:1.0.0")
        self.assertTrue(result.network)
        self.assertTrue(result.connection)
        self.assertEqual(result.containers, 2)  # 3 - 1 for cargo
        self.assertEqual(result.bridges, 2)

    def test_client_status_cargo_not_found(self):
        """Test client status when cargo container is not found"""
        from docker.errors import NotFound

        self.config.DOCKER.containers.get.side_effect = NotFound("Container not found")
        self.config.DOCKER.networks.get.side_effect = NotFound("Network not found")

        result = _get_client_status(self.config)

        self.assertFalse(result.cargo)
        self.assertEqual(result.version, "")
        self.assertFalse(result.network)
        self.assertFalse(result.connection)
        self.assertEqual(result.containers, 0)
        self.assertEqual(result.bridges, 0)

    def test_client_status_cargo_not_running(self):
        """Test client status when cargo container exists but is not running"""
        from docker.errors import NotFound

        cargo_container = Mock()
        cargo_container.status = "stopped"
        self.config.DOCKER.containers.get.return_value = cargo_container
        self.config.DOCKER.networks.get.side_effect = NotFound("Network not found")

        result = _get_client_status(self.config)

        self.assertFalse(result.cargo)

    def test_client_status_network_not_found(self):
        """Test client status when network is not found"""
        from docker.errors import NotFound

        cargo_container = Mock()
        cargo_container.status = "running"
        cargo_container.attrs = {
            "Config": {
                "Labels": {
                    CARGO_ENDPOINT_LABEL: "192.168.1.1:51820",
                    VERSION_LABEL: "1.0.0",
                }
            }
        }
        cargo_container.image.tags = ["gefyra/cargo:1.0.0"]
        self.config.DOCKER.containers.get.return_value = cargo_container
        self.config.DOCKER.networks.get.side_effect = NotFound("Network not found")

        result = _get_client_status(self.config)

        self.assertTrue(result.cargo)
        self.assertFalse(result.network)

    @patch("gefyra.local.cargo.probe_wireguard_connection")
    def test_client_status_wireguard_connection_failed(self, mock_probe_wg):
        """Test client status when wireguard connection probe fails"""
        cargo_container = Mock()
        cargo_container.status = "running"
        cargo_container.attrs = {
            "Config": {
                "Labels": {
                    CARGO_ENDPOINT_LABEL: "192.168.1.1:51820",
                    VERSION_LABEL: "1.0.0",
                }
            }
        }
        cargo_container.image.tags = ["gefyra/cargo:1.0.0"]
        self.config.DOCKER.containers.get.return_value = cargo_container

        network = Mock()
        network.containers = [Mock()]
        self.config.DOCKER.networks.get.return_value = network

        mock_probe_wg.side_effect = RuntimeError("Connection failed")

        result = _get_client_status(self.config)

        self.assertTrue(result.cargo)
        self.assertTrue(result.network)
        self.assertFalse(result.connection)

    def test_client_status_containers_count_without_cargo(self):
        """Test container count when cargo is not running"""
        from docker.errors import NotFound

        self.config.DOCKER.containers.get.side_effect = NotFound("Container not found")

        network = Mock()
        network.containers = [Mock(), Mock()]  # 2 containers
        self.config.DOCKER.networks.get.return_value = network

        result = _get_client_status(self.config)

        self.assertFalse(result.cargo)
        self.assertTrue(result.network)
        self.assertEqual(result.containers, 2)  # No subtraction since cargo not running


class TestGetClusterStatus(unittest.TestCase):
    """Tests for _get_cluster_status function"""

    def setUp(self):
        self.config = MagicMock()
        self.config.NAMESPACE = "gefyra"

    def test_cluster_status_all_running(self):
        """Test cluster status when everything is running"""
        # Mock API resources check
        self.config.K8S_CORE_API.get_api_resources.return_value = Mock()

        # Mock namespace
        self.config.K8S_CORE_API.read_namespace.return_value = Mock()

        # Mock operator deployment
        operator_deploy = Mock()
        operator_deploy.status.ready_replicas = 1
        operator_deploy.spec.template.spec.containers = [
            Mock(image="gefyra/operator:1.0.0")
        ]
        self.config.K8S_APP_API.read_namespaced_deployment.return_value = (
            operator_deploy
        )

        # Mock stowaway pod
        stowaway_pod = Mock()
        stowaway_pod.status.container_statuses = [Mock(ready=True)]
        stowaway_pod.spec.containers = [Mock(image="gefyra/stowaway:1.0.0")]
        self.config.K8S_CORE_API.read_namespaced_pod.return_value = stowaway_pod

        result = _get_cluster_status(self.config)

        self.assertTrue(result.connected)
        self.assertTrue(result.namespace)
        self.assertTrue(result.operator)
        self.assertEqual(result.operator_image, "gefyra/operator:1.0.0")
        self.assertTrue(result.stowaway)
        self.assertEqual(result.stowaway_image, "gefyra/stowaway:1.0.0")
        self.assertTrue(result.operator_webhook)

    def test_cluster_status_not_connected(self):
        """Test cluster status when not connected to cluster"""
        from kubernetes.client import ApiException

        self.config.K8S_CORE_API.get_api_resources.side_effect = ApiException(
            status=401
        )

        result = _get_cluster_status(self.config)

        self.assertFalse(result.connected)
        self.assertFalse(result.operator)
        self.assertFalse(result.stowaway)
        self.assertFalse(result.namespace)

    def test_cluster_status_config_exception(self):
        """Test cluster status when config exception occurs"""
        from kubernetes.config import ConfigException

        self.config.K8S_CORE_API.get_api_resources.side_effect = ConfigException()

        result = _get_cluster_status(self.config)

        self.assertFalse(result.connected)

    def test_cluster_status_max_retry_error(self):
        """Test cluster status when max retry error occurs"""
        error = urllib3.exceptions.MaxRetryError(pool=Mock(), url="http://test")
        self.config.K8S_CORE_API.get_api_resources.side_effect = error

        result = _get_cluster_status(self.config)

        self.assertFalse(result.connected)

    def test_cluster_status_namespace_not_found(self):
        """Test cluster status when namespace is not found"""
        from kubernetes.client import ApiException

        self.config.K8S_CORE_API.get_api_resources.return_value = Mock()
        self.config.K8S_CORE_API.read_namespace.side_effect = ApiException(status=404)

        result = _get_cluster_status(self.config)

        self.assertTrue(result.connected)
        self.assertFalse(result.namespace)
        self.assertFalse(result.operator)

    def test_cluster_status_operator_not_ready(self):
        """Test cluster status when operator is not ready"""

        self.config.K8S_CORE_API.get_api_resources.return_value = Mock()
        self.config.K8S_CORE_API.read_namespace.return_value = Mock()

        operator_deploy = Mock()
        operator_deploy.status.ready_replicas = 0
        self.config.K8S_APP_API.read_namespaced_deployment.return_value = (
            operator_deploy
        )

        result = _get_cluster_status(self.config)

        self.assertTrue(result.connected)
        self.assertTrue(result.namespace)
        self.assertFalse(result.operator)

    def test_cluster_status_operator_not_found(self):
        """Test cluster status when operator deployment is not found"""
        from kubernetes.client import ApiException

        self.config.K8S_CORE_API.get_api_resources.return_value = Mock()
        self.config.K8S_CORE_API.read_namespace.return_value = Mock()
        self.config.K8S_APP_API.read_namespaced_deployment.side_effect = ApiException(
            status=404
        )

        result = _get_cluster_status(self.config)

        self.assertTrue(result.connected)
        self.assertTrue(result.namespace)
        self.assertFalse(result.operator)

    def test_cluster_status_stowaway_not_ready(self):
        """Test cluster status when stowaway is not ready"""
        self.config.K8S_CORE_API.get_api_resources.return_value = Mock()
        self.config.K8S_CORE_API.read_namespace.return_value = Mock()

        operator_deploy = Mock()
        operator_deploy.status.ready_replicas = 1
        operator_deploy.spec.template.spec.containers = [
            Mock(image="gefyra/operator:1.0.0")
        ]
        self.config.K8S_APP_API.read_namespaced_deployment.return_value = (
            operator_deploy
        )

        stowaway_pod = Mock()
        stowaway_pod.status.container_statuses = [Mock(ready=False)]
        stowaway_pod.spec.containers = [Mock(image="gefyra/stowaway:1.0.0")]
        self.config.K8S_CORE_API.read_namespaced_pod.return_value = stowaway_pod

        result = _get_cluster_status(self.config)

        self.assertTrue(result.operator)
        self.assertFalse(result.stowaway)

    def test_cluster_status_stowaway_not_found(self):
        """Test cluster status when stowaway pod is not found"""
        from kubernetes.client import ApiException

        self.config.K8S_CORE_API.get_api_resources.return_value = Mock()
        self.config.K8S_CORE_API.read_namespace.return_value = Mock()

        operator_deploy = Mock()
        operator_deploy.status.ready_replicas = 1
        operator_deploy.spec.template.spec.containers = [
            Mock(image="gefyra/operator:1.0.0")
        ]
        self.config.K8S_APP_API.read_namespaced_deployment.return_value = (
            operator_deploy
        )

        self.config.K8S_CORE_API.read_namespaced_pod.side_effect = ApiException(
            status=404
        )

        result = _get_cluster_status(self.config)

        self.assertTrue(result.operator)
        self.assertFalse(result.stowaway)


class TestStatus(unittest.TestCase):
    """Tests for status function"""

    @patch("gefyra.api.status._get_client_status")
    @patch("gefyra.api.status._get_cluster_status")
    @patch("gefyra.api.status.ClientConfiguration")
    def test_status_summary_up(
        self, mock_config_class, mock_cluster_status, mock_client_status
    ):
        """Test status returns UP when client has connection"""
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        client_status = Mock()
        client_status.connection = True
        mock_client_status.return_value = client_status

        cluster_status = Mock()
        mock_cluster_status.return_value = cluster_status

        result = status(connection_name="test")

        self.assertEqual(result.summary, StatusSummary.UP)
        self.assertEqual(result.client, client_status)
        self.assertEqual(result.cluster, cluster_status)

    @patch("gefyra.api.status._get_client_status")
    @patch("gefyra.api.status._get_cluster_status")
    @patch("gefyra.api.status.ClientConfiguration")
    def test_status_summary_incomplete_with_cargo(
        self, mock_config_class, mock_cluster_status, mock_client_status
    ):
        """Test status returns INCOMPLETE when cargo is running but no connection"""
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        client_status = Mock()
        client_status.connection = False
        client_status.cargo = True
        mock_client_status.return_value = client_status

        cluster_status = Mock()
        cluster_status.connected = False
        mock_cluster_status.return_value = cluster_status

        result = status(connection_name="test")

        self.assertEqual(result.summary, StatusSummary.INCOMPLETE)

    @patch("gefyra.api.status._get_client_status")
    @patch("gefyra.api.status._get_cluster_status")
    @patch("gefyra.api.status.ClientConfiguration")
    def test_status_summary_incomplete_cluster_ready(
        self, mock_config_class, mock_cluster_status, mock_client_status
    ):
        """Test status returns INCOMPLETE when cluster is ready but no client connection"""
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        client_status = Mock()
        client_status.connection = False
        client_status.cargo = False
        mock_client_status.return_value = client_status

        cluster_status = Mock()
        cluster_status.connected = True
        cluster_status.operator = True
        cluster_status.stowaway = True
        cluster_status.operator_webhook = True
        mock_cluster_status.return_value = cluster_status

        result = status(connection_name="test")

        self.assertEqual(result.summary, StatusSummary.INCOMPLETE)

    @patch("gefyra.api.status._get_client_status")
    @patch("gefyra.api.status._get_cluster_status")
    @patch("gefyra.api.status.ClientConfiguration")
    def test_status_summary_down(
        self, mock_config_class, mock_cluster_status, mock_client_status
    ):
        """Test status returns DOWN when nothing is running"""
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        client_status = Mock()
        client_status.connection = False
        client_status.cargo = False
        mock_client_status.return_value = client_status

        cluster_status = Mock()
        cluster_status.connected = False
        cluster_status.operator = False
        cluster_status.stowaway = False
        cluster_status.operator_webhook = False
        mock_cluster_status.return_value = cluster_status

        result = status(connection_name="test")

        self.assertEqual(result.summary, StatusSummary.DOWN)

    @patch("gefyra.api.status._get_client_status")
    @patch("gefyra.api.status._get_cluster_status")
    @patch("gefyra.api.status.ClientConfiguration")
    def test_status_max_retry_error_raises_client_config_error(
        self, mock_config_class, mock_cluster_status, mock_client_status
    ):
        """Test status raises ClientConfigurationError on MaxRetryError"""
        from gefyra.exceptions import ClientConfigurationError

        mock_config = MagicMock()
        mock_config.KUBE_CONFIG_FILE = "/path/to/kubeconfig"
        mock_config_class.return_value = mock_config

        cluster_status = Mock()
        mock_cluster_status.return_value = cluster_status

        pool = Mock()
        pool.host = "192.168.1.1"
        pool.port = 6443
        error = urllib3.exceptions.MaxRetryError(pool=pool, url="http://test")
        mock_client_status.side_effect = error

        with self.assertRaises(ClientConfigurationError) as context:
            status(connection_name="test")

        self.assertIn("Cannot reach cluster", str(context.exception))
        self.assertIn("192.168.1.1", str(context.exception))

    @patch("gefyra.api.status._get_client_status")
    @patch("gefyra.api.status._get_cluster_status")
    @patch("gefyra.api.status.ClientConfiguration")
    def test_status_default_connection_name(
        self, mock_config_class, mock_cluster_status, mock_client_status
    ):
        """Test status uses default connection name when not provided"""
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        client_status = Mock()
        client_status.connection = True
        mock_client_status.return_value = client_status

        cluster_status = Mock()
        mock_cluster_status.return_value = cluster_status

        result = status()

        mock_config_class.assert_called_once_with(connection_name="")
        self.assertEqual(result.summary, StatusSummary.UP)

    @patch("gefyra.api.status._get_client_status")
    @patch("gefyra.api.status._get_cluster_status")
    @patch("gefyra.api.status.ClientConfiguration")
    def test_status_partial_cluster_ready(
        self, mock_config_class, mock_cluster_status, mock_client_status
    ):
        """Test status returns DOWN when cluster is only partially ready"""
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        client_status = Mock()
        client_status.connection = False
        client_status.cargo = False
        mock_client_status.return_value = client_status

        # Only some cluster components are ready
        cluster_status = Mock()
        cluster_status.connected = True
        cluster_status.operator = True
        cluster_status.stowaway = False  # Stowaway not ready
        cluster_status.operator_webhook = True
        mock_cluster_status.return_value = cluster_status

        result = status(connection_name="test")

        # Should be DOWN because not all cluster components are ready
        self.assertEqual(result.summary, StatusSummary.DOWN)


if __name__ == "__main__":
    unittest.main()
