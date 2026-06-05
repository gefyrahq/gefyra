import base64
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import MagicMock, patch, AsyncMock

from kubernetes.client import ApiException

from gefyra.bridge_mount import utils


class TestBridgeMountUtils(TestCase):
    def setUp(self):
        utils._K8S_SECRET_CACHE.clear()
        self.mock_api = MagicMock()
        self.original_get_api = utils._get_core_v1_api
        utils._get_core_v1_api = MagicMock(return_value=self.mock_api)

    def tearDown(self):
        utils._get_core_v1_api = self.original_get_api

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
        result = utils._read_k8s_secret_tls_value(
            secret_name, secret_key, secret_namespace
        )
        self.assertEqual(result, secret_value)
        self.mock_api.read_namespaced_secret.assert_called_once_with(
            secret_name, secret_namespace
        )

        # Second call - should hit cache
        self.mock_api.reset_mock()
        result = utils._read_k8s_secret_tls_value(
            secret_name, secret_key, secret_namespace
        )
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
        utils._read_k8s_secret_tls_value(secret_name, secret_key, secret_namespace)

        # Mock time to be 61 seconds later
        with patch("time.time") as mock_time:
            # We need to simulate the initial time and then the later time
            initial_time = 1000.0
            mock_time.return_value = initial_time
            # Re-run initial call to set initial time in cache
            utils._K8S_SECRET_CACHE.clear()
            utils._read_k8s_secret_tls_value(secret_name, secret_key, secret_namespace)

            mock_time.return_value = initial_time + 61
            self.mock_api.reset_mock()
            result = utils._read_k8s_secret_tls_value(
                secret_name, secret_key, secret_namespace
            )
            self.assertEqual(result, secret_value)
            self.mock_api.read_namespaced_secret.assert_called_once()

    def test_read_k8s_secret_tls_value_not_found(self):
        self.mock_api.read_namespaced_secret.side_effect = ApiException(
            status=404, reason="Not Found"
        )

        with self.assertRaises(Exception) as cm:
            utils._read_k8s_secret_tls_value("missing", "key")
        self.assertIn("Failed to read secret", str(cm.exception))

    def test_read_k8s_secret_tls_value_missing_key(self):
        mock_secret = MagicMock()
        mock_secret.data = {"other-key": "value"}
        self.mock_api.read_namespaced_secret.return_value = mock_secret

        with self.assertRaises(Exception) as cm:
            utils._read_k8s_secret_tls_value("my-secret", "missing-key")
        self.assertIn("Key 'missing-key' not found", str(cm.exception))

    def test_tls_param_from_key_secret(self):
        params = {
            "80": {"tls": {"certificate": {"secret": {"name": "cert-secret"}}}},
            "tls": {"key": {"secret": {"name": "key-secret"}}},
        }

        # Specific port
        self.assertTrue(utils._tls_param_from_key_secret("certificate", params, 80))
        # Default port (key is not in 80, so it should fall back to global tls)
        self.assertTrue(utils._tls_param_from_key_secret("key", params, 80))
        # No rport
        self.assertTrue(utils._tls_param_from_key_secret("key", params))
        # Missing
        self.assertFalse(utils._tls_param_from_key_secret("other", params))

    def test_get_tls_from_provider_parameters(self):
        params = {
            "80": {
                "tls": {
                    "certificate": {"secret": {"name": "cert-secret"}},
                    "key": "direct-key",
                    "sni": {
                        "secret": {
                            "name": "sni-secret",
                            "key": "sni",
                            "namespace": "default",
                        }
                    },
                }
            }
        }

        secret_value = "sni-content"
        encoded_value = base64.b64encode(secret_value.encode("utf-8")).decode("utf-8")
        mock_secret = MagicMock()
        mock_secret.data = {"sni": encoded_value}
        self.mock_api.read_namespaced_secret.return_value = mock_secret

        tls_config = utils._get_tls_from_provider_parameters(params, 80)
        self.assertEqual(
            tls_config.certificate, utils.INJECTED_TLS_CERT.format(port="80")
        )
        self.assertEqual(tls_config.key, "direct-key")
        self.assertEqual(tls_config.sni, "sni-content")

        # No TLS
        self.assertIsNone(utils._get_tls_from_provider_parameters({}, 80))


class TestBridgeMountUtilsAsync(IsolatedAsyncioTestCase):
    def setUp(self):
        utils._K8S_SECRET_CACHE.clear()
        self.mock_api = MagicMock()
        self.original_get_api = utils._get_core_v1_api
        utils._get_core_v1_api = MagicMock(return_value=self.mock_api)

        # Default secret mock
        self.secret_content = "cert-content"
        encoded_value = base64.b64encode(self.secret_content.encode("utf-8")).decode(
            "utf-8"
        )
        self.mock_secret = MagicMock()
        self.mock_secret.data = {"k": encoded_value}
        self.mock_api.read_namespaced_secret.return_value = self.mock_secret

        # Aggressive mock for inject_tls_file
        self.original_inject = utils.inject_tls_file
        self.mock_inject = AsyncMock()
        utils.inject_tls_file = self.mock_inject

    def tearDown(self):
        utils._get_core_v1_api = self.original_get_api
        utils.inject_tls_file = self.original_inject

    @patch("gefyra.bridge.carrier2.utils.read_carrier2_file")
    async def test_update_tls_file(self, mock_read_file):
        logger = MagicMock()
        params = {
            "tls": {
                "certificate": {"secret": {"name": "s", "key": "k", "namespace": "n"}}
            }
        }

        # Should update (content mismatch)
        mock_read_file.return_value = ["old-content"]
        updated = await utils.update_tls_file(
            logger, "pod", "container", "ns", "certificate", params
        )
        self.assertTrue(updated)
        self.mock_inject.assert_called_once()

        # Should not update (content match)
        self.mock_inject.reset_mock()
        mock_read_file.return_value = [self.secret_content]
        updated = await utils.update_tls_file(
            logger, "pod", "container", "ns", "certificate", params
        )
        self.assertFalse(updated)
        self.mock_inject.assert_not_called()

    @patch("gefyra.bridge_mount.utils.wait_until_condition")
    @patch("gefyra.bridge.carrier2.utils.stream_exec_retries")
    async def test_inject_tls_file(self, mock_stream, mock_wait):
        # We need to use the REAL inject_tls_file here
        utils.inject_tls_file = self.original_inject

        logger = MagicMock()
        params = {
            "tls": {
                "certificate": {"secret": {"name": "s", "key": "k", "namespace": "n"}}
            }
        }

        container = MagicMock()
        container.name = "nginx"

        await utils.inject_tls_file(logger, "pod", "nginx", "ns", "certificate", params)

        mock_stream.assert_called_once()
        args = mock_stream.call_args[0]
        self.assertIn(
            f"cat <<'EOF' > /tmp/from_k8s_secret_cert_all.pem\n{self.secret_content}",
            args[4][0],
        )

        # Restore mock for other tests
        utils.inject_tls_file = self.mock_inject
