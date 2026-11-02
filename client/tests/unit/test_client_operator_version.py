import unittest
import warnings
from unittest.mock import MagicMock, patch

from gefyra.api.status import status
from gefyra.cluster.utils import (
    client_operator_version_mismatch_message,
    image_ref_to_tag,
    normalize_gefyra_version,
    warn_client_operator_version_mismatch,
)


class TestImageRefToTag(unittest.TestCase):
    def test_simple_image(self):
        self.assertEqual(image_ref_to_tag("quay.io/gefyra/operator:2.5.6"), "2.5.6")

    def test_registry_with_port(self):
        self.assertEqual(
            image_ref_to_tag("localhost:5000/gefyra/operator:2.5.6"), "2.5.6"
        )

    def test_missing_tag(self):
        self.assertIsNone(image_ref_to_tag("quay.io/gefyra/operator"))


class TestClientOperatorVersionMismatchMessage(unittest.TestCase):
    @patch("gefyra.cluster.utils.__VERSION__", "2.5.6")
    def test_matching_versions(self):
        self.assertIsNone(
            client_operator_version_mismatch_message("quay.io/gefyra/operator:2.5.6")
        )

    @patch("gefyra.cluster.utils.__VERSION__", "2.5.6")
    def test_matching_versions_with_dashes(self):
        self.assertIsNone(
            client_operator_version_mismatch_message("quay.io/gefyra/operator:2-5-6")
        )

    @patch("gefyra.cluster.utils.__VERSION__", "2.5.6")
    def test_mismatch(self):
        message = client_operator_version_mismatch_message(
            "quay.io/gefyra/operator:2.4.0"
        )
        self.assertIn("2.5.6", message)
        self.assertIn("2.4.0", message)
        self.assertIn("gefyra operator update", message)

    def test_normalize_gefyra_version(self):
        self.assertEqual(normalize_gefyra_version("2-5-6"), "2.5.6")


class TestWarnClientOperatorVersionMismatch(unittest.TestCase):
    @patch("gefyra.cluster.utils.__VERSION__", "2.5.6")
    def test_emits_warning_on_mismatch(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            warn_client_operator_version_mismatch("quay.io/gefyra/operator:2.4.0")
        self.assertEqual(len(caught), 1)
        self.assertIn("2.4.0", str(caught[0].message))

    @patch("gefyra.cluster.utils.__VERSION__", "2.5.6")
    def test_no_warning_when_matching(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            warn_client_operator_version_mismatch("quay.io/gefyra/operator:2.5.6")
        self.assertEqual(len(caught), 0)


class TestStatusVersionMismatchWarning(unittest.TestCase):
    @patch("gefyra.api.status._get_client_status")
    @patch("gefyra.api.status._get_cluster_status")
    @patch("gefyra.api.status.ClientConfiguration")
    @patch("gefyra.cluster.utils.__VERSION__", "2.5.6")
    def test_status_warns_on_operator_mismatch(
        self, mock_config_cls, mock_cluster_status, mock_client_status
    ):
        from gefyra.types import GefyraClientStatus, GefyraClusterStatus, StatusSummary

        mock_config_cls.return_value = MagicMock()
        mock_cluster_status.return_value = GefyraClusterStatus(
            connected=True,
            operator=True,
            operator_image="quay.io/gefyra/operator:2.4.0",
            stowaway=True,
            stowaway_image="quay.io/gefyra/stowaway:2.4.0",
            namespace=True,
            operator_webhook=True,
        )
        mock_client_status.return_value = GefyraClientStatus(
            cargo=False,
            version="",
            cargo_image="",
            network=False,
            connection=False,
            containers=0,
            bridges=0,
            kubeconfig="",
            context="",
            cargo_endpoint="",
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = status()

        self.assertEqual(result.summary, StatusSummary.INCOMPLETE)
        self.assertEqual(len(caught), 1)
        self.assertIn("2.4.0", str(caught[0].message))
