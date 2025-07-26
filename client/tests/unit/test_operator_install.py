from unittest import TestCase
from unittest.mock import patch

import pytest

from click.testing import CliRunner


@pytest.mark.usefixtures("monkeypatch")
class GefyraOperatorInstallTest(TestCase):

    @patch("gefyra.misc.comps.deployment.data")
    def test_operator_install(self, mock_deployment_data):
        from gefyra.cli.main import cli

        runner = CliRunner()
        runner.invoke(
            cli,
            ["install", "--apply", "--stowaway-max-connection-age", "5"],
            catch_exceptions=False,
        )

        # Verify deployment.data() was called with the correct stowaway_max_connection_age
        mock_deployment_data.assert_called()
        call_args = mock_deployment_data.call_args
        params = call_args[0][0]  # First positional argument should be params
        assert params.stowaway_max_connection_age == "5"
