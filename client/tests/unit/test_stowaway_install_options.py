import json
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner


@pytest.mark.parametrize(
    "field,value",
    [
        ("stowaway_node_selector", []),
        ("stowaway_node_selector", {"pool": True}),
        ("stowaway_node_selector", {"bad/key/name": "pool"}),
        ("stowaway_node_selector", {"UPPER.example/pool": "pool"}),
        ("stowaway_pod_labels", {"pool": "bad value"}),
        ("stowaway_pod_labels", {"gefyra.dev/app": "other"}),
        ("stowaway_tolerations", {}),
        ("stowaway_tolerations", [{"key": "dedicated", "unknown": "bad"}]),
        ("stowaway_tolerations", [{"operator": "Equal"}]),
        ("stowaway_tolerations", [{"key": "pool", "operator": "Exists", "value": "x"}]),
        ("stowaway_tolerations", [{"key": "pool", "effect": "Invalid"}]),
        (
            "stowaway_tolerations",
            [{"key": "pool", "effect": "NoSchedule", "tolerationSeconds": 2}],
        ),
        (
            "stowaway_tolerations",
            [{"key": "pool", "effect": "NoExecute", "tolerationSeconds": True}],
        ),
        ("stowaway_startup_probe_failure_threshold", 0),
        ("stowaway_startup_probe_failure_threshold", -1),
        ("stowaway_startup_probe_failure_threshold", True),
        ("stowaway_startup_probe_failure_threshold", 1.5),
        ("stowaway_startup_probe_failure_threshold", "60"),
    ],
)
def test_invalid_python_inputs(field, value):
    from gefyra.types import GefyraInstallOptions

    with pytest.raises(ValueError):
        GefyraInstallOptions(**{field: value})


def test_options_and_defaults_are_independent():
    from gefyra.types import GefyraInstallOptions

    first = GefyraInstallOptions()
    second = GefyraInstallOptions()
    first.stowaway_node_selector["pool"] = "one"
    assert second.stowaway_node_selector == {}
    assert second.stowaway_tolerations == []
    assert second.stowaway_pod_labels == {}
    assert second.stowaway_startup_probe_failure_threshold == 3


def test_cli_serializes_structured_options():
    from gefyra.cli.main import cli
    from gefyra.misc.install import synthesize_config_as_yaml
    from gefyra.types import GefyraInstallOptions

    arguments = {
        "stowaway_node_selector": {"example.com/pool": "gefyra"},
        "stowaway_tolerations": [
            {
                "key": "dedicated",
                "operator": "Equal",
                "value": "gefyra",
                "effect": "NoSchedule",
            }
        ],
        "stowaway_pod_labels": {
            "example.com/workload": "gefyra",
            "gefyra.dev/app": "stowaway",
        },
        "stowaway_startup_probe_failure_threshold": 60,
    }
    flags = []
    for name, value in arguments.items():
        flags.extend(["--" + name.replace("_", "-"), json.dumps(value)])
    with patch("gefyra.configuration.ClientConfiguration"):
        result = CliRunner().invoke(cli, ["install", *flags], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    actual = list(yaml.safe_load_all(result.output))
    expected = list(
        yaml.safe_load_all(synthesize_config_as_yaml(GefyraInstallOptions(**arguments)))
    )
    assert actual == expected
    deployments = [item for item in actual if item["kind"] == "Deployment"]
    for deployment in deployments:
        spec = deployment["spec"]["template"]["spec"]
        assert "nodeSelector" not in spec
        assert "tolerations" not in spec
        env = {item["name"]: item["value"] for item in spec["containers"][0]["env"]}
        for name, value in arguments.items():
            assert json.loads(env["GEFYRA_" + name.upper()]) == value
    service = next(
        item
        for item in actual
        if item["kind"] == "Service"
        and item["metadata"]["name"] == "gefyra-stowaway-wireguard"
    )
    assert "example.com/workload" not in service["spec"]["selector"]


@pytest.mark.parametrize(
    "flag,value",
    [
        ("--stowaway-startup-probe-failure-threshold", "0"),
        ("--stowaway-startup-probe-failure-threshold", "-1"),
        ("--stowaway-startup-probe-failure-threshold", "1.5"),
        ("--stowaway-node-selector", "{broken"),
        ("--stowaway-node-selector", "null"),
        ("--stowaway-tolerations", "{}"),
        ("--stowaway-pod-labels", '{"gefyra.dev/app":"other"}'),
    ],
)
def test_cli_rejects_invalid_values(flag, value):
    from gefyra.cli.main import cli

    with patch("gefyra.configuration.ClientConfiguration"):
        result = CliRunner().invoke(cli, ["install", flag, value])
    assert result.exit_code != 0
    assert "Error" in result.output


def test_explicit_empty_settings_override_preset(monkeypatch):
    from gefyra.api.install import LB_PRESETS
    from gefyra.cli.main import cli
    from gefyra.types import GefyraInstallOptions

    monkeypatch.setitem(
        LB_PRESETS,
        "placement",
        GefyraInstallOptions(
            stowaway_node_selector={"pool": "old"},
            stowaway_pod_labels={"custom": "old"},
            stowaway_tolerations=[{"operator": "Exists"}],
        ),
    )
    with (
        patch("gefyra.configuration.ClientConfiguration"),
        patch("gefyra.misc.comps.deployment.data", return_value=[]) as render,
    ):
        result = CliRunner().invoke(
            cli,
            [
                "install",
                "--preset",
                "placement",
                "--stowaway-node-selector",
                "{}",
                "--stowaway-tolerations",
                "[]",
                "--stowaway-pod-labels",
                "{}",
            ],
        )
    assert result.exit_code == 0, result.output
    options = render.call_args.args[0]
    assert options.stowaway_node_selector == {}
    assert options.stowaway_tolerations == []
    assert options.stowaway_pod_labels == {}
