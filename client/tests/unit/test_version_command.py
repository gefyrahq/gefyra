from click.testing import CliRunner

from gefyra.cli.main import cli


def test_version_command():
    runner = CliRunner()
    result = runner.invoke(cli, ["version"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "Gefyra client version" in result.output


def test_version_command_no_check():
    runner = CliRunner()
    result = runner.invoke(cli, ["version", "-n"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "Gefyra client version" in result.output
