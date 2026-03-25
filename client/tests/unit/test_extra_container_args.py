import pytest
import click
from unittest import TestCase
from click.testing import CliRunner

from gefyra.cli.utils import parse_extra_container_args


class TestParseExtraContainerArgs:
    """Tests for the parse_extra_container_args helper."""

    def test_empty_list(self):
        assert parse_extra_container_args([]) == {}

    def test_single_key_value(self):
        result = parse_extra_container_args(["--cpu-shares", "512"])
        assert result == {"cpu_shares": 512}

    def test_multiple_key_values(self):
        result = parse_extra_container_args(
            ["--cpu-shares", "512", "--mem-reservation", "256m"]
        )
        assert result == {"cpu_shares": 512, "mem_reservation": "256m"}

    def test_boolean_flag(self):
        result = parse_extra_container_args(["--oom-kill-disable"])
        assert result == {"oom_kill_disable": True}

    def test_boolean_flag_with_other_args(self):
        result = parse_extra_container_args(
            ["--oom-kill-disable", "--cpu-shares", "512"]
        )
        assert result == {"oom_kill_disable": True, "cpu_shares": 512}

    def test_equals_syntax(self):
        result = parse_extra_container_args(["--cpu-shares=512"])
        assert result == {"cpu_shares": 512}

    def test_equals_syntax_with_string_value(self):
        result = parse_extra_container_args(["--restart=always"])
        assert result == {"restart": "always"}

    def test_float_coercion(self):
        result = parse_extra_container_args(["--cpu-count", "1.5"])
        assert result == {"cpu_count": 1.5}

    def test_bool_coercion_true(self):
        result = parse_extra_container_args(["--privileged", "true"])
        assert result == {"privileged": True}

    def test_bool_coercion_false(self):
        result = parse_extra_container_args(["--privileged", "false"])
        assert result == {"privileged": False}

    def test_string_value_preserved(self):
        result = parse_extra_container_args(["--restart", "unless-stopped"])
        assert result == {"restart": "unless-stopped"}

    def test_invalid_arg_no_dashes(self):
        with pytest.raises(click.UsageError, match="must start with '--'"):
            parse_extra_container_args(["cpu-shares", "512"])

    def test_mixed_equals_and_positional(self):
        result = parse_extra_container_args(
            ["--cpu-shares=512", "--mem-limit", "1g", "--oom-kill-disable"]
        )
        assert result == {
            "cpu_shares": 512,
            "mem_limit": "1g",
            "oom_kill_disable": True,
        }

    def test_hyphen_to_underscore_conversion(self):
        result = parse_extra_container_args(["--memory-swap", "2g"])
        assert result == {"memory_swap": "2g"}

    def test_single_word_flag(self):
        result = parse_extra_container_args(["--init"])
        assert result == {"init": True}

    def test_integer_zero(self):
        result = parse_extra_container_args(["--cpu-shares", "0"])
        assert result == {"cpu_shares": 0}


class TestRunCommandExtraArgs:
    """Test that the run CLI command properly handles extra args."""

    def test_help_shows_extra_args_info(self):
        from gefyra.cli.run import run

        runner = CliRunner()
        result = runner.invoke(run, ["--help"])
        assert "container engine arguments" in result.output

    def test_unknown_option_does_not_fail_parsing(self):
        """Verify that unknown options don't cause a Click error at parse time."""
        from gefyra.cli.run import run

        runner = CliRunner()
        # This will fail at runtime (no connection), but should NOT fail at
        # Click parse time with "no such option: --cpu-shares"
        result = runner.invoke(
            run,
            [
                "-i",
                "alpine",
                "-N",
                "test",
                "--",
                "--cpu-shares",
                "512",
            ],
        )
        # Should fail with connection error, NOT "no such option"
        assert "no such option" not in (result.output or "").lower()
