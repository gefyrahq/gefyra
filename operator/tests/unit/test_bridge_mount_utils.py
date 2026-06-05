import base64
from unittest import TestCase
from unittest.mock import patch, MagicMock
from gefyra.bridge_mount.utils import _read_k8s_secret_tls_value, _K8S_SECRET_CACHE


class TestBridgeMountUtils(TestCase):
    def setUp(self):
        _K8S_SECRET_CACHE.clear()
        self.mock_api_patcher = patch("gefyra.bridge_mount.utils.core_v1_api")
        self.mock_api = self.mock_api_patcher.start()

    def tearDown(self):
        self.mock_api_patcher.stop()

    def test_read_k8s_secret_tls_value_success(self):
        secret_name = "test-secret"
        secret_key = "cert.pem"
        secret_namespace = "test-ns"
        secret_value = "secret-content"
        encoded_value = base64.b64encode(secret_value.encode("utf-8")).decode("utf-8")

        mock_secret = MagicMock()
        mock_secret.data = {secret_key: encoded_value}
        self.mock_api.read_namespaced_secret.return_value = mock_secret

        # First call - should hit API
        result = _read_k8s_secret_tls_value(secret_name, secret_key, secret_namespace)
        self.assertEqual(result, secret_value)
        self.mock_api.read_namespaced_secret.assert_called_once_with(
            secret_name, secret_namespace
        )

        # Second call - should hit cache
        self.mock_api.reset_mock()
        result = _read_k8s_secret_tls_value(secret_name, secret_key, secret_namespace)
        self.assertEqual(result, secret_value)
        self.mock_api.read_namespaced_secret.assert_not_called()

    def test_read_k8s_secret_tls_value_cache_expiry(self):
        secret_name = "test-secret"
        secret_key = "cert.pem"
        secret_namespace = "test-ns"
        secret_value = "secret-content"
        encoded_value = base64.b64encode(secret_value.encode("utf-8")).decode("utf-8")

        mock_secret = MagicMock()
        mock_secret.data = {secret_key: encoded_value}
        self.mock_api.read_namespaced_secret.return_value = mock_secret

        # Initial call
        _read_k8s_secret_tls_value(secret_name, secret_key, secret_namespace)

        # Mock time to be 61 seconds later
        with patch("time.time") as mock_time:
            # We need to simulate the initial time and then the later time
            initial_time = 1000.0
            mock_time.return_value = initial_time
            # Re-run initial call to set initial time in cache
            _K8S_SECRET_CACHE.clear()
            _read_k8s_secret_tls_value(secret_name, secret_key, secret_namespace)

            mock_time.return_value = initial_time + 61
            self.mock_api.reset_mock()
            result = _read_k8s_secret_tls_value(
                secret_name, secret_key, secret_namespace
            )
            self.assertEqual(result, secret_value)
            self.mock_api.read_namespaced_secret.assert_called_once()

    def test_read_k8s_secret_tls_value_not_found(self):
        from kubernetes.client import ApiException

        self.mock_api.read_namespaced_secret.side_effect = ApiException(
            status=404, reason="Not Found"
        )

        with self.assertRaises(Exception) as cm:
            _read_k8s_secret_tls_value("missing", "key")
        self.assertIn("Failed to read secret", str(cm.exception))

    def test_read_k8s_secret_tls_value_missing_key(self):
        mock_secret = MagicMock()
        mock_secret.data = {"other-key": "value"}
        self.mock_api.read_namespaced_secret.return_value = mock_secret

        with self.assertRaises(Exception) as cm:
            _read_k8s_secret_tls_value("my-secret", "missing-key")
        self.assertIn("Key 'missing-key' not found", str(cm.exception))
