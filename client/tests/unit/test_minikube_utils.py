import pytest
from gefyra.local.minikube import _get_a_worker_ip
import gefyra.local.minikube as minikube_helpers


def test_get_a_worker_ip():
    config = {"Nodes": []}
    with pytest.raises(
        RuntimeError, match="This Minikube cluster does not have a worker node."
    ):
        _get_a_worker_ip(config)


def test_detect_minikube_config_for_invalid_driver(monkeypatch):
    # monkeypatch _read_minikube_config in minikube_helpers to return a dict 'config' with an invalid driver
    config = {"Driver": "invalid_driver"}
    monkeypatch.setattr(minikube_helpers, "_read_minikube_config", lambda x: config)
    with pytest.raises(
        RuntimeError,
        match="Gefyra does not support Minikube with this driver invalid_driver",
    ):
        minikube_helpers.detect_minikube_config("someprofile")


def test_detect_minikube_config_with_missing_network(monkeypatch):
    # monkeypatch _read_minikube_config in minikube_helpers to return a dict 'config' with an invalid driver
    config = {
        "Driver": "docker",
        "Nodes": [{"IP": "something", "Worker": True}],
        "Name": "Unit Test",
    }
    monkeypatch.setattr(minikube_helpers, "_read_minikube_config", lambda x: config)
    params = minikube_helpers.detect_minikube_config("someprofile")
    assert params["network_name"] == "minikube"
