import json
from time import sleep
import pytest
from pytest_kubernetes.providers import AClusterManager


def test_a_create_client(operator: AClusterManager):
    k3d = operator
    k3d.apply("tests/fixtures/a_gefyra_client.yaml")

    k3d.wait(
        "gefyraclients.gefyra.dev/client-a",
        "jsonpath=.state=WAITING",
        namespace="gefyra",
        timeout=20,
    )
    client_a = k3d.kubectl(
        ["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"]
    )
    assert client_a["state"] == "WAITING"
    assert client_a["stateTransitions"]["CREATING"] is not None


def test_b_client_waiting(operator: AClusterManager):
    k3d = operator
    k3d.wait(
        "gefyraclients.gefyra.dev/client-a",
        "jsonpath=.state=WAITING",
        namespace="gefyra",
        timeout=20,
    )
    client_a = k3d.kubectl(
        ["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"]
    )
    assert client_a["state"] == "WAITING"
    assert client_a["stateTransitions"]["CREATING"] is not None


def test_c_client_activate(operator: AClusterManager):
    k3d = operator
    patch = json.dumps({"providerParameter": {"subnet": "192.168.101.0/24"}})
    k3d.kubectl(
        [
            "-n",
            "gefyra",
            "patch",
            "gefyraclient",
            "client-a",
            "--type='merge'",
            f"--patch='{patch}'",
        ]
    )
    k3d.wait(
        "gefyraclients.gefyra.dev/client-a",
        "jsonpath=.state=ENABLING",
        namespace="gefyra",
        timeout=20,
    )
    client_a = k3d.kubectl(
        ["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"]
    )
    assert client_a["providerParameter"] is not None
    k3d.wait(
        "gefyraclients.gefyra.dev/client-a",
        "jsonpath=.state=ACTIVE",
        namespace="gefyra",
        timeout=20,
    )
    client_a = k3d.kubectl(
        ["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"]
    )
    assert client_a["state"] == "ACTIVE"
    assert client_a.get("stateTransitions") is not None
    assert client_a["providerConfig"] is not None

    service_accounts = k3d.kubectl(
        ["-n", "gefyra", "get", "serviceaccount"], as_dict=False
    )
    assert "gefyra-client-client-a" in service_accounts


def test_d_client_deactivate(operator: AClusterManager):
    k3d = operator
    patch = json.dumps({"providerParameter": None})
    k3d.kubectl(
        [
            "-n",
            "gefyra",
            "patch",
            "gefyraclient",
            "client-a",
            "--type='merge'",
            f"--patch='{patch}'",
        ]
    )
    client_a = k3d.kubectl(
        ["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"]
    )
    assert "providerParameter" not in client_a
    sleep(1)
    k3d.wait(
        "gefyraclients.gefyra.dev/client-a",
        "jsonpath=.state=DISABLING",
        namespace="gefyra",
        timeout=20,
    )
    k3d.wait(
        "gefyraclients.gefyra.dev/client-a",
        "jsonpath=.state=WAITING",
        namespace="gefyra",
        timeout=20,
    )
    client_a = k3d.kubectl(
        ["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"]
    )
    assert client_a["state"] == "WAITING"
    assert client_a.get("stateTransitions") is not None
    assert client_a.get("providerConfig") is None


def test_e_client_reactivate(operator: AClusterManager):
    k3d = operator
    patch = json.dumps({"providerParameter": {"subnet": "192.168.101.0/24"}})
    k3d.kubectl(
        [
            "-n",
            "gefyra",
            "patch",
            "gefyraclient",
            "client-a",
            "--type='merge'",
            f"--patch='{patch}'",
        ]
    )
    k3d.wait(
        "gefyraclients.gefyra.dev/client-a",
        "jsonpath=.state=ENABLING",
        namespace="gefyra",
        timeout=20,
    )
    client_a = k3d.kubectl(
        ["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"]
    )
    assert client_a["providerParameter"] is not None
    k3d.wait(
        "gefyraclients.gefyra.dev/client-a",
        "jsonpath=.state=ACTIVE",
        namespace="gefyra",
        timeout=20,
    )
    client_a = k3d.kubectl(
        ["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"]
    )
    assert client_a["state"] == "ACTIVE"
    assert client_a.get("stateTransitions") is not None
    assert client_a["providerConfig"] is not None


def test_f_delete_client(operator: AClusterManager):
    k3d = operator
    k3d.kubectl(
        [
            "-n",
            "gefyra",
            "delete",
            "gefyraclient",
            "client-a",
        ],
        as_dict=False,
    )
    with pytest.raises(RuntimeError):
        k3d.kubectl(["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"])

    service_accounts = k3d.kubectl(["-n", "gefyra", "get", "serviceaccount"])
    assert "gefyra-client-client-a" not in service_accounts
