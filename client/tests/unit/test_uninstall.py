import unittest
from unittest.mock import Mock, patch
import kubernetes.client.exceptions

from gefyra.misc.uninstall import (
    remove_all_clients,
    remove_remainder_bridges,
    remove_gefyra_namespace,
    remove_gefyra_crds,
    remove_gefyra_rbac,
)
from gefyra.configuration import ClientConfiguration


class TestRemoveAllClients(unittest.TestCase):
    """Tests for remove_all_clients function"""

    @patch("gefyra.misc.uninstall.logger")
    @patch("gefyra.api.clients.delete_client")
    @patch("gefyra.api.clients.list_client")
    def test_remove_all_clients_success(
        self, mock_list_client, mock_delete_client, mock_logger
    ):
        """Test removing all clients successfully"""
        # Setup mock clients
        client1 = Mock(client_id="client-1")
        client2 = Mock(client_id="client-2")
        mock_list_client.return_value = [client1, client2]

        # Execute
        remove_all_clients()

        # Verify
        mock_list_client.assert_called_once()
        assert mock_delete_client.call_count == 2
        mock_delete_client.assert_any_call("client-1", force=True, wait=True)
        mock_delete_client.assert_any_call("client-2", force=True, wait=True)

    @patch("gefyra.api.clients.delete_client")
    @patch("gefyra.api.clients.list_client")
    def test_remove_all_clients_empty_list(self, mock_list_client, mock_delete_client):
        """Test when there are no clients to remove"""
        mock_list_client.return_value = []

        remove_all_clients()

        mock_list_client.assert_called_once()
        mock_delete_client.assert_not_called()

    @patch("gefyra.api.clients.delete_client")
    @patch("gefyra.api.clients.list_client")
    def test_remove_all_clients_deletion_error(
        self, mock_list_client, mock_delete_client
    ):
        """Test error handling during client deletion"""
        client1 = Mock(client_id="client-1")
        mock_list_client.return_value = [client1]
        mock_delete_client.side_effect = Exception("Deletion failed")

        with self.assertRaises(Exception):
            remove_all_clients()

        mock_delete_client.assert_called_once_with("client-1", force=True, wait=True)


class TestRemoveRemainderBridges(unittest.TestCase):
    """Tests for remove_remainder_bridges function"""

    def setUp(self):
        self.config = Mock(spec=ClientConfiguration)
        self.config.NAMESPACE = "gefyra"
        self.config.K8S_CUSTOM_OBJECT_API = Mock()

    def test_remove_remainder_bridges_success(self):
        """Test removing bridges successfully"""
        # Setup mock data
        bridges_response = {
            "items": [
                {
                    "metadata": {"name": "bridge-1"},
                },
                {
                    "metadata": {"name": "bridge-2"},
                },
            ]
        }
        self.config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object.return_value = (
            bridges_response
        )

        # Execute
        result = remove_remainder_bridges(self.config)

        # Verify
        self.assertIsNone(result)
        self.config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object.assert_called_once_with(
            group="gefyra.dev",
            version="v1",
            namespace="gefyra",
            plural="gefyrabridges",
        )
        # Verify patch and delete called for each bridge
        assert (
            self.config.K8S_CUSTOM_OBJECT_API.patch_namespaced_custom_object.call_count
            == 2
        )
        assert (
            self.config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object.call_count
            == 2
        )

    def test_remove_remainder_bridges_no_bridges(self):
        """Test when there are no bridges to remove"""
        bridges_response = {"items": []}
        self.config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object.return_value = (
            bridges_response
        )

        result = remove_remainder_bridges(self.config)

        self.assertIsNone(result)
        self.config.K8S_CUSTOM_OBJECT_API.patch_namespaced_custom_object.assert_not_called()
        self.config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object.assert_not_called()

    def test_remove_remainder_bridges_list_fails(self):
        """Test when listing bridges fails"""
        self.config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object.side_effect = (
            Exception("List failed")
        )

        result = remove_remainder_bridges(self.config)

        self.assertIsNone(result)

    def test_remove_remainder_bridges_patch_fails_continues(self):
        """Test that patch failure is caught and continues to next bridge"""
        bridges_response = {
            "items": [
                {"metadata": {"name": "bridge-1"}},
                {"metadata": {"name": "bridge-2"}},
            ]
        }
        self.config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object.return_value = (
            bridges_response
        )
        self.config.K8S_CUSTOM_OBJECT_API.patch_namespaced_custom_object.side_effect = (
            Exception("Patch failed")
        )

        result = remove_remainder_bridges(self.config)

        self.assertIsNone(result)
        # Both bridges should be attempted despite patch failure
        assert (
            self.config.K8S_CUSTOM_OBJECT_API.patch_namespaced_custom_object.call_count
            == 2
        )

    def test_remove_remainder_bridges_delete_fails_continues(self):
        """Test that delete failure is caught and continues to next bridge"""
        bridges_response = {
            "items": [
                {"metadata": {"name": "bridge-1"}},
                {"metadata": {"name": "bridge-2"}},
            ]
        }
        self.config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object.return_value = (
            bridges_response
        )
        self.config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object.side_effect = Exception(
            "Delete failed"
        )

        result = remove_remainder_bridges(self.config)

        self.assertIsNone(result)
        # Both deletes should be attempted
        assert (
            self.config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object.call_count
            == 2
        )

    def test_remove_remainder_bridges_patch_params(self):
        """Test correct parameters are passed to patch"""
        bridges_response = {
            "items": [
                {"metadata": {"name": "test-bridge"}},
            ]
        }
        self.config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object.return_value = (
            bridges_response
        )

        remove_remainder_bridges(self.config)

        self.config.K8S_CUSTOM_OBJECT_API.patch_namespaced_custom_object.assert_called_once_with(
            group="gefyra.dev",
            version="v1",
            plural="gefyrabridges",
            namespace="gefyra",
            name="test-bridge",
            body={"metadata": {"finalizers": None}},
        )

    def test_remove_remainder_bridges_delete_params(self):
        """Test correct parameters are passed to delete"""
        bridges_response = {
            "items": [
                {"metadata": {"name": "test-bridge"}},
            ]
        }
        self.config.K8S_CUSTOM_OBJECT_API.list_namespaced_custom_object.return_value = (
            bridges_response
        )

        remove_remainder_bridges(self.config)

        self.config.K8S_CUSTOM_OBJECT_API.delete_namespaced_custom_object.assert_called_once_with(
            group="gefyra.dev",
            version="v1",
            plural="gefyrabridges",
            namespace="gefyra",
            name="test-bridge",
        )


class TestRemoveGefyraNamespace(unittest.TestCase):
    """Tests for remove_gefyra_namespace function"""

    def setUp(self):
        self.config = Mock(spec=ClientConfiguration)
        self.config.NAMESPACE = "gefyra"
        self.config.K8S_CORE_API = Mock()

    def test_remove_gefyra_namespace_success(self):
        """Test removing namespace successfully"""
        remove_gefyra_namespace(self.config)

        self.config.K8S_CORE_API.delete_namespace.assert_called_once_with(name="gefyra")

    def test_remove_gefyra_namespace_not_found_404(self):
        """Test that 404 error is silently ignored"""
        error = kubernetes.client.exceptions.ApiException(status=404)
        self.config.K8S_CORE_API.delete_namespace.side_effect = error

        # Should not raise
        remove_gefyra_namespace(self.config)

        self.config.K8S_CORE_API.delete_namespace.assert_called_once_with(name="gefyra")

    def test_remove_gefyra_namespace_other_error_raises(self):
        """Test that non-404 errors are re-raised"""
        error = kubernetes.client.exceptions.ApiException(status=403)
        self.config.K8S_CORE_API.delete_namespace.side_effect = error

        with self.assertRaises(kubernetes.client.exceptions.ApiException):
            remove_gefyra_namespace(self.config)

    def test_remove_gefyra_namespace_500_error_raises(self):
        """Test that 500 errors are re-raised"""
        error = kubernetes.client.exceptions.ApiException(status=500)
        self.config.K8S_CORE_API.delete_namespace.side_effect = error

        with self.assertRaises(kubernetes.client.exceptions.ApiException):
            remove_gefyra_namespace(self.config)


class TestRemoveGefyraCRDs(unittest.TestCase):
    """Tests for remove_gefyra_crds function"""

    def setUp(self):
        self.config = Mock(spec=ClientConfiguration)
        self.config.K8S_EXTENSION_API = Mock()

    def test_remove_gefyra_crds_success(self):
        """Test removing CRDs successfully"""
        remove_gefyra_crds(self.config)

        expected_crds = ["gefyrabridges.gefyra.dev", "gefyraclients.gefyra.dev"]
        assert (
            self.config.K8S_EXTENSION_API.delete_custom_resource_definition.call_count
            == 2
        )
        for crd in expected_crds:
            self.config.K8S_EXTENSION_API.delete_custom_resource_definition.assert_any_call(
                name=crd
            )

    def test_remove_gefyra_crds_api_error_ignored(self):
        """Test that ApiException is silently ignored"""
        error = kubernetes.client.exceptions.ApiException(status=404)
        self.config.K8S_EXTENSION_API.delete_custom_resource_definition.side_effect = (
            error
        )

        # Should not raise
        remove_gefyra_crds(self.config)

        assert (
            self.config.K8S_EXTENSION_API.delete_custom_resource_definition.call_count
            == 2
        )

    def test_remove_gefyra_crds_partial_failure(self):
        """Test that failure to delete one CRD doesn't stop deletion of others"""
        error = kubernetes.client.exceptions.ApiException(status=404)
        self.config.K8S_EXTENSION_API.delete_custom_resource_definition.side_effect = [
            error,
            None,
        ]

        remove_gefyra_crds(self.config)

        assert (
            self.config.K8S_EXTENSION_API.delete_custom_resource_definition.call_count
            == 2
        )


class TestRemoveGefyraRBAC(unittest.TestCase):
    """Tests for remove_gefyra_rbac function"""

    def setUp(self):
        self.config = Mock(spec=ClientConfiguration)
        self.config.K8S_RBAC_API = Mock()
        self.config.K8S_ADMISSION_API = Mock()

    @patch("gefyra.misc.uninstall.logger")
    def test_remove_gefyra_rbac_success(self, mock_logger):
        """Test removing RBAC resources successfully"""
        remove_gefyra_rbac(self.config)

        # Verify cluster roles
        self.config.K8S_RBAC_API.delete_cluster_role.assert_called_once_with(
            name="gefyra:operator"
        )

        # Verify cluster role bindings
        self.config.K8S_RBAC_API.delete_cluster_role_binding.assert_called_once_with(
            name="gefyra-operator"
        )

        # Verify webhooks
        self.config.K8S_ADMISSION_API.delete_validating_webhook_configuration.assert_called_once_with(
            name="gefyra.dev"
        )

        # Verify no logger.debug calls on success
        mock_logger.debug.assert_not_called()

    @patch("gefyra.misc.uninstall.logger")
    def test_remove_gefyra_rbac_cluster_role_error_logged(self, mock_logger):
        """Test that cluster role deletion error is logged"""
        error = kubernetes.client.exceptions.ApiException(status=404)
        self.config.K8S_RBAC_API.delete_cluster_role.side_effect = error

        remove_gefyra_rbac(self.config)

        # Verify logger.debug was called with the exception
        mock_logger.debug.assert_called_once_with(error)

    @patch("gefyra.misc.uninstall.logger")
    def test_remove_gefyra_rbac_cluster_role_binding_error_logged(self, mock_logger):
        """Test that cluster role binding deletion error is logged"""
        error = kubernetes.client.exceptions.ApiException(status=404)
        self.config.K8S_RBAC_API.delete_cluster_role_binding.side_effect = error

        remove_gefyra_rbac(self.config)

        # Verify logger.debug was called with the exception
        mock_logger.debug.assert_called_once_with(error)

    @patch("gefyra.misc.uninstall.logger")
    def test_remove_gefyra_rbac_webhook_error_logged(self, mock_logger):
        """Test that webhook deletion error is logged"""
        error = kubernetes.client.exceptions.ApiException(status=404)
        self.config.K8S_ADMISSION_API.delete_validating_webhook_configuration.side_effect = error

        remove_gefyra_rbac(self.config)

        # Verify logger.debug was called with the exception
        mock_logger.debug.assert_called_once_with(error)

    @patch("gefyra.misc.uninstall.logger")
    def test_remove_gefyra_rbac_all_errors_logged(self, mock_logger):
        """Test that all errors are logged"""
        error1 = kubernetes.client.exceptions.ApiException(status=404)
        error2 = kubernetes.client.exceptions.ApiException(status=403)
        error3 = kubernetes.client.exceptions.ApiException(status=500)

        self.config.K8S_RBAC_API.delete_cluster_role.side_effect = error1
        self.config.K8S_RBAC_API.delete_cluster_role_binding.side_effect = error2
        self.config.K8S_ADMISSION_API.delete_validating_webhook_configuration.side_effect = error3

        remove_gefyra_rbac(self.config)

        # Verify logger.debug was called 3 times
        assert mock_logger.debug.call_count == 3
        mock_logger.debug.assert_any_call(error1)
        mock_logger.debug.assert_any_call(error2)
        mock_logger.debug.assert_any_call(error3)

    @patch("gefyra.misc.uninstall.logger")
    def test_remove_gefyra_rbac_continues_on_error(self, mock_logger):
        """Test that deletion continues even after errors"""
        error = kubernetes.client.exceptions.ApiException(status=404)
        self.config.K8S_RBAC_API.delete_cluster_role.side_effect = error

        remove_gefyra_rbac(self.config)

        # Verify all delete calls were attempted
        self.config.K8S_RBAC_API.delete_cluster_role.assert_called_once()
        self.config.K8S_RBAC_API.delete_cluster_role_binding.assert_called_once()
        self.config.K8S_ADMISSION_API.delete_validating_webhook_configuration.assert_called_once()


if __name__ == "__main__":
    unittest.main()
