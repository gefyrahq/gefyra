import json
from gefyra.types import GefyraClientConfig
# Python
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from gefyra.cli.clients import clients


@pytest.fixture
def runner():
    # Keep stderr separate to avoid brittle assertions; tests handle both streams
    return CliRunner(mix_stderr=False)


def invoke_with_obj(runner: CliRunner, args, obj=None, env=None):
    if obj is None:
        obj = {"kubeconfig": None, "context": None}
    return runner.invoke(clients, args, obj=obj, env=env)


# 1) Pass-through of all options to API when echoing to stdout (no -o)
@patch("gefyra.api.write_client_file")
def test_client_config_pass_through_stdout(mock_write, runner: CliRunner):
    mock_json = '{"client":"ok"}'
    mock_write.return_value = mock_json
    obj = {"kubeconfig": "/k", "context": "ctx"}

    result = invoke_with_obj(
        runner,
        [
            "config",
            "my-client",
            "--host",
            "h.example",
            "--port",
            "5555",
            "--kube-api",
            "https://kube:6443",
            "--registry",
            "r.example",
            "--mtu",
            "1400",
            "--local",
        ],
        obj=obj,
    )

    assert result.exit_code == 0, (result.output, result.stderr)
    mock_write.assert_called_once_with(
        "my-client",
        host="h.example",
        port=5555,
        kube_api="https://kube:6443",
        kubeconfig="/k",
        kubecontext="ctx",
        registry="r.example",
        wireguard_mtu=1400,
        local=True,
    )
    # Printed to stdout by click.echo (with trailing newline)
    assert mock_json in result.output


# 2) Default MTU and no optional args provided
@patch("gefyra.api.write_client_file")
def test_client_config_defaults(mock_write, runner: CliRunner):
    mock_write.return_value = "{}"

    result = invoke_with_obj(
        runner,
        ["config", "client-1"],
        obj={"kubeconfig": "/k", "context": None},
    )

    assert result.exit_code == 0
    mock_write.assert_called_once_with(
        "client-1",
        host=None,
        port=None,
        kube_api=None,
        kubeconfig="/k",
        kubecontext=None,
        registry=None,
        wireguard_mtu=1340,  # default from the CLI option
        local=False,
    )


# 3) Kubeconfig resolution from environment when ctx.obj has None
@patch("gefyra.api.write_client_file")
def test_client_config_kubeconfig_from_env_when_missing_in_ctx(
    mock_write, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("KUBECONFIG", "/env/kube.conf")

    result = invoke_with_obj(
        runner,
        ["config", "client-env"],
        obj={"kubeconfig": None, "context": "ctx-from-obj"},
        env={"KUBECONFIG": "/env/kube.conf"},
    )

    assert result.exit_code == 0
    mock_write.assert_called_once_with(
        "client-env",
        host=None,
        port=None,
        kube_api=None,
        kubeconfig="/env/kube.conf",
        kubecontext="ctx-from-obj",
        registry=None,
        wireguard_mtu=1340,
        local=False,
    )


# 4) Default kubeconfig path when neither ctx.obj nor env provides it
@patch("gefyra.api.write_client_file")
def test_client_config_uses_default_kubeconfig_when_ctx_and_env_missing(
    mock_write, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("KUBECONFIG", raising=False)
    # Ensure deterministic default
    monkeypatch.setattr(
        "os.path.expanduser",
        lambda p: "/home/user/.kube/config" if p == "~/.kube/config" else p,
    )

    result = invoke_with_obj(
        runner,
        ["config", "client-default"],
        obj={"kubeconfig": None, "context": "c"},
    )

    assert result.exit_code == 0
    mock_write.assert_called_once_with(
        "client-default",
        host=None,
        port=None,
        kube_api=None,
        kubeconfig="/home/user/.kube/config",
        kubecontext="c",
        registry=None,
        wireguard_mtu=1340,
        local=False,
    )


# 5) Output written to file when -o/--output is provided
@patch("gefyra.api.write_client_file")
def test_client_config_writes_to_file(mock_write, runner: CliRunner, tmp_path: Path):
    mock_json = '{"cfg":"value"}'
    mock_write.return_value = mock_json
    outfile = tmp_path / "client.json"

    result = invoke_with_obj(
        runner,
        ["config", "client-out", "-o", str(outfile)],
        obj={"kubeconfig": "/k", "context": "ctx"},
    )

    assert result.exit_code == 0, (result.output, result.stderr)
    # Should not echo JSON to stdout when output file is provided
    assert mock_json not in result.output
    # File should contain the JSON content
    assert outfile.read_text(encoding="utf-8") == mock_json


# 6) Error propagation via standard_error_handler formatting
@patch("gefyra.api.write_client_file", side_effect=RuntimeError("cfg-boom"))
def test_client_config_error_is_printed_and_nonzero_exit(mock_write, runner: CliRunner):
    result = invoke_with_obj(
        runner,
        ["config", "client-x"],
        obj={"kubeconfig": "/k", "context": "ctx"},
    )
    assert result.exit_code != 0
    # Safely combine streams: stderr might not be captured separately
    try:
        stderr_text = result.stderr or ""
    except Exception:
        stderr_text = ""
    combined = (result.output or "") + stderr_text
    assert "error: cfg-boom" in combined.lower()


# 7) Help text shows expected options
def test_client_config_help_shows_expected_options(runner: CliRunner):
    res = runner.invoke(
        clients, ["config", "--help"], obj={"kubeconfig": None, "context": None}
    )
    assert res.exit_code == 0
    out = res.output.lower()
    for opt in ("--host", "--port", "--kube-api", "--registry", "--mtu", "--local", "--output"):
        assert opt in out


def test_read_client_config():
    payload = {
        "client_id": "client-a",
        "kubernetes_server": "https://gefyra.dev",
        "provider": "stowaway",
        "token": "some-token",
        "namespace": "my_ms",
        "ca_crt": "ca_cert",
        "gefyra_server": "https://gefyra.dev",
        "registry": "https://quay.io",
        "wireguard_mtu": 1320,
    }
    GefyraClientConfig.from_json_str(json.dumps(payload))


def test_read_client_config_optionals_missing():
    payload = {
        "client_id": "client-a",
        "kubernetes_server": "https://gefyra.dev",
        "provider": "stowaway",
        "token": "some-token",
        "namespace": "my_ms",
        "ca_crt": "ca_cert",
        "gefyra_server": "https://gefyra.dev",
    }
    GefyraClientConfig.from_json_str(json.dumps(payload))
