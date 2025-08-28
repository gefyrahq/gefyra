from unittest import TestCase
from unittest.mock import patch

from click.testing import CliRunner


class GefyraOperatorInstallTest(TestCase):

    @patch("gefyra.misc.comps.deployment.data")
    def test_operator_install_connection_age(self, mock_deployment_data):
        from gefyra.cli.main import cli

        runner = CliRunner()
        runner.invoke(
            cli,
            ["install", "--apply", "--max-client-connection-age", "5"],
            catch_exceptions=False,
        )

        # Verify deployment.data() was called with the correct stowaway_max_connection_age
        mock_deployment_data.assert_called()
        call_args = mock_deployment_data.call_args
        params = call_args[0][0]  # First positional argument should be params
        assert params.max_client_connection_age == "5"

    @patch("gefyra.misc.comps.deployment.data")
    def test_operator_install_sa_management(self, mock_deployment_data):
        from gefyra.cli.main import cli

        runner = CliRunner()
        runner.invoke(
            cli,
            ["install", "--apply", "--disable-client-sa-management"],
            catch_exceptions=False,
        )

        # Verify deployment.data() was called with the correct stowaway_max_connection_age
        mock_deployment_data.assert_called()
        call_args = mock_deployment_data.call_args
        params = call_args[0][0]  # First positional argument should be params
        assert params.disable_client_sa_management is True
