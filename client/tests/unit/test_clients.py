from time import sleep
from gefyra.types import GefyraClientState
import pytest
from pytest_kubernetes.providers import AClusterManager


def test_a_create_client(operator: AClusterManager):
    k3d = operator
    from gefyra.api.clients import add_clients

    gclient = add_clients("client-a", kubeconfig=operator.kubeconfig)
    client_a = k3d.kubectl(
        ["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"]
    )
    assert client_a["state"] is not None
    with pytest.raises(RuntimeError):
        gclient.get_client_config(gefyra_server="localhost:31820")
    k3d.wait(
        "gefyraclients.gefyra.dev/client-a",
        "jsonpath=.state=WAITING",
        namespace="gefyra",
        timeout=20,
    )
    assert gclient.state is GefyraClientState.WAITING


def test_b_get_client(operator: AClusterManager):
    k3d = operator
    from gefyra.api.clients import get_client

    gclient = get_client("client-a", kubeconfig=operator.kubeconfig)
    retries = 10
    counter = 0
    try:
        assert gclient.state is GefyraClientState.WAITING
    except AssertionError as e:
        if counter >= retries:
            raise e
        counter += 1
        sleep(2)

    assert gclient.provider_parameter is None
    assert gclient.provider_config is None
    k3d.kubectl(["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"])
    config = gclient.get_client_config(gefyra_server="localhost:31820")
    assert config.kubernetes_server is not None
    assert config.ca_crt is not None
    assert config.namespace is not None
    assert config.token is not None


def test_c_create_clients(operator: AClusterManager):
    k3d = operator
    k3d.version()
    from gefyra.api.clients import add_clients

    for client in ["client-b", "client-c", "client-d", "client-e", "client-f"]:
        add_clients(client, kubeconfig=operator.kubeconfig)


def test_d_delete_client(operator: AClusterManager):
    k3d = operator
    from gefyra.api.clients import delete_client

    delete_client("client-f", kubeconfig=operator.kubeconfig)
    sleep(2)
    with pytest.raises(RuntimeError):
        k3d.kubectl(["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-f"])
