from pytest_kubernetes.providers import AClusterManager


def test_a_create_client(operator: AClusterManager):
    k3d = operator 
    k3d.apply("tests/fixtures/a_gefyra_client.yaml")

    k3d.wait(
        "gefyraclients.gefyra.dev/client-a",
        "jsonpath=.state=CREATING",
        namespace="gefyra",
        timeout=20,
    )
    client_a = k3d.kubectl(["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"])
    assert client_a["state"] == "CREATING"
    assert client_a["stateTransitions"]["CREATING"] is not None


    

