# Python
import os
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner

# Import the click group defined for clients
from gefyra.cli.clients import clients
from tests.factories import ClientIdFactory


@pytest.fixture
def runner():
    return CliRunner(mix_stderr=True)


def invoke_with_obj(runner: CliRunner, args, obj=None, env=None):
    """
    Helper to invoke the click group with an object keeping kubeconfig/context.
    """
    if obj is None:
        obj = {"kubeconfig": None, "context": None}
    result = runner.invoke(clients, args, obj=obj, env=env)
    return result


@patch("gefyra.cli.clients.console.success")
@patch("gefyra.api.add_clients")
def test_create_clients_with_quantity_and_registry_calls_api(
    mock_add_clients, mock_success, runner: CliRunner
):
    # Arrange
    client_id = None
    quantity = 3
    registry = "registry.example.com"
    kubeconfig = "/tmp/kube/config"
    kubecontext = "my-context"

    # Act
    result = invoke_with_obj(
        runner,
        ["create", "-n", str(quantity), "--registry", registry],
        obj={"kubeconfig": kubeconfig, "context": kubecontext},
    )

    # Assert
    assert result.exit_code == 0, result.output
    mock_add_clients.assert_called_once_with(
        client_id,
        quantity,
        registry=registry,
        kubeconfig=kubeconfig,
        kubecontext=kubecontext,
    )
    mock_success.assert_called_once()
    # Verify success message includes created count
    assert "3 client(s) created successfully" in "".join(
        str(call.args[0]) for call in mock_success.call_args_list
    )


@patch("gefyra.cli.clients.console.success")
@patch("gefyra.api.add_clients")
def test_create_clients_with_explicit_client_id_uses_default_quantity_1(
    mock_add_clients, mock_success, runner: CliRunner
):
    # Arrange
    cid = ClientIdFactory()
    kubeconfig = "/some/kubeconfig"
    kubecontext = None

    # Act
    result = invoke_with_obj(
        runner,
        ["create", "--client-id", cid],
        obj={"kubeconfig": kubeconfig, "context": kubecontext},
    )

    # Assert
    assert result.exit_code == 0, result.output
    mock_add_clients.assert_called_once_with(
        cid, 1, registry=None, kubeconfig=kubeconfig, kubecontext=kubecontext
    )
    mock_success.assert_called_once()
    assert "1 client(s) created successfully" in "".join(
        str(call.args[0]) for call in mock_success.call_args_list
    )


@patch("gefyra.cli.clients.console.success")
@patch("gefyra.api.add_clients")
def test_create_clients_kubeconfig_sourced_from_env_when_missing_in_ctx(
    mock_add_clients, mock_success, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
):
    # Arrange
    env_kubeconfig = "/env/kube/config"
    monkeypatch.setenv("KUBECONFIG", env_kubeconfig)

    # Context object provides None for kubeconfig to trigger env sourcing
    obj = {"kubeconfig": None, "context": "ctx-from-test"}

    # Act
    result = invoke_with_obj(runner, ["create"], obj=obj)

    # Assert
    assert result.exit_code == 0, result.output
    # Quantity defaults to 1, client_id is None, registry is None
    mock_add_clients.assert_called_once_with(
        None, 1, registry=None, kubeconfig=env_kubeconfig, kubecontext="ctx-from-test"
    )
    mock_success.assert_called_once()
    assert "1 client(s) created successfully" in "".join(
        str(call.args[0]) for call in mock_success.call_args_list
    )


@patch("gefyra.cli.clients.console.success")
@patch("gefyra.api.add_clients", side_effect=RuntimeError("Error!"))
def test_create_clients_propagates_errors_through_standard_error_handler(
    mock_add_clients, mock_success, runner: CliRunner
):
    # Arrange
    # Provide explicit kubeconfig/context in obj
    obj = {"kubeconfig": "/kube/config", "context": "ctx"}

    # Act
    result = invoke_with_obj(runner, ["create"], obj=obj)

    # Assert
    assert result.exit_code != 0
    # Error text should be visible to the user
    assert "error!" in result.output.lower()
    mock_success.assert_not_called()

# Both client-id and quantity provided: current behavior is pass-through (no validation)
@patch("gefyra.cli.clients.console.success")
@patch("gefyra.api.add_clients")
def test_create_with_client_id_and_quantity_passes_through(
    mock_add_clients, mock_success, runner: CliRunner
):
    cid = ClientIdFactory()
    kubeconfig = "/tmp/kube/config"
    kubecontext = "ctx"

    result = invoke_with_obj(
        runner,
        ["create", "--client-id", cid, "-n", "5"],
        obj={"kubeconfig": kubeconfig, "context": kubecontext},
    )

    assert result.exit_code == 0, result.output
    mock_add_clients.assert_called_once_with(
        cid, 5, registry=None, kubeconfig=kubeconfig, kubecontext=kubecontext
    )
    # success should mention the requested quantity
    success_text = "".join(str(call.args[0]) for call in mock_success.call_args_list)
    assert "5 client(s) created successfully" in success_text


# Quantity = 0: current behavior is pass-through to API (no validation)
@patch("gefyra.cli.clients.console.success")
@patch("gefyra.api.add_clients")
def test_create_with_zero_quantity_passes_through(
    mock_add_clients, mock_success, runner: CliRunner
):
    result = invoke_with_obj(
        runner,
        ["create", "-n", "0"],
        obj={"kubeconfig": "/k", "context": "c"},
    )

    assert result.exit_code == 0, (result.output, result.stderr)
    mock_add_clients.assert_called_once_with(
        None, 0, registry=None, kubeconfig="/k", kubecontext="c"
    )
    success_text = "".join(str(call.args[0]) for call in mock_success.call_args_list)
    assert "0 client(s) created successfully" in success_text


# Large quantity: pass-through and message
@patch("gefyra.cli.clients.console.success")
@patch("gefyra.api.add_clients")
def test_create_with_large_quantity_passes_through(
    mock_add_clients, mock_success, runner: CliRunner
):
    qty = 1000
    result = invoke_with_obj(
        runner,
        ["create", "-n", str(qty)],
        obj={"kubeconfig": "/k", "context": "c"},
    )

    assert result.exit_code == 0
    mock_add_clients.assert_called_once_with(
        None, qty, registry=None, kubeconfig="/k", kubecontext="c"
    )
    success_text = "".join(str(call.args[0]) for call in mock_success.call_args_list)
    assert f"{qty} client(s) created successfully" in success_text


# Default kubeconfig path when none provided and env missing
@patch("gefyra.cli.clients.console.success")
@patch("gefyra.api.add_clients")
def test_create_uses_default_kubeconfig_when_ctx_and_env_missing(
    mock_add_clients, mock_success, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
):
    # Ensure env var is not set
    monkeypatch.delenv("KUBECONFIG", raising=False)
    # Force a deterministic default path
    monkeypatch.setattr(
        "os.path.expanduser",
        lambda p: "/home/user/.kube/config" if p == "~/.kube/config" else p,
    )

    result = invoke_with_obj(
        runner,
        ["create"],
        obj={"kubeconfig": None, "context": "ctx-from-obj"},
    )

    assert result.exit_code == 0, (result.output, result.stderr)
    mock_add_clients.assert_called_once_with(
        None,
        1,
        registry=None,
        kubeconfig="/home/user/.kube/config",
        kubecontext="ctx-from-obj",
    )
    mock_success.assert_called_once()


# API raises ClickException directly: should propagate with Click formatting
@patch("gefyra.cli.clients.console.success")
@patch("gefyra.api.add_clients", side_effect=click.ClickException("boom-click"))
def test_create_clients_clickexception_is_propagated(
    mock_add_clients, mock_success, runner: CliRunner
):
    result = invoke_with_obj(
        runner,
        ["create"],
        obj={"kubeconfig": "/k", "context": "c"},
    )
    assert result.exit_code != 0
    # Safely combine streams: stderr may not be separately captured
    try:
        stderr_text = result.stderr or ""
    except Exception:
        stderr_text = ""
    combined = (result.output or "") + stderr_text

    mock_add_clients.assert_called_once_with(
        None, 1, registry=None, kubeconfig="/k", kubecontext="c"
    )

    assert "error: boom-click" in combined.lower()
    mock_success.assert_not_called()


# Help text for group and subcommand shows expected options
def test_clients_group_help_shows_create_and_options(runner: CliRunner):
    # Provide ctx.obj so group callback can access it safely
    res = runner.invoke(clients, ["--help"], obj={"kubeconfig": None, "context": None})
    assert res.exit_code == 0
    out = res.output.lower()
    assert "create" in out

    res_create = runner.invoke(
        clients, ["create", "--help"], obj={"kubeconfig": None, "context": None}
    )
    assert res_create.exit_code == 0
    outc = res_create.output.lower()
    assert "--client-id" in outc
    assert "-n" in outc or "--quantity" in outc
    assert "--registry" in outc



# Success message reflects quantity exactly
@patch("gefyra.cli.clients.console.success")
@patch("gefyra.api.add_clients")
def test_create_success_message_reflects_quantity(
    mock_add_clients, mock_success, runner: CliRunner
):
    result = invoke_with_obj(
        runner,
        ["create", "-n", "2"],
        obj={"kubeconfig": "/k", "context": "c"},
    )
    assert result.exit_code == 0
    success_text = "".join(str(call.args[0]) for call in mock_success.call_args_list)
    assert "2 client(s) created successfully" in success_text


