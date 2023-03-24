from time import sleep
from pytest_kubernetes.providers import AClusterManager


def test_a_boot_operator(operator: AClusterManager):
    k8s = operator
    namespaces = k8s.kubectl(["get", "ns"], as_dict=False)
    assert "gefyra" in namespaces
    # deployments = k8s.kubectl(["get", "deployments", "-n", "gefyra"])

    # assert len(deployments["items"]) == 1
    # assert deployments["items"][0]["metadata"]["name"] == "gefyra-stowaway"
    # k8s.wait(
    #     "deployments/gefyra-stowaway",
    #     "condition=Available=True",
    #     namespace="gefyra",
    #     timeout=90,
    # )
    events = k8s.kubectl(["get", "events", "-n", "gefyra"])
    _i = 0
    while len(events["items"]) < 8 and _i < 10:
        sleep(1)
        events = k8s.kubectl(["get", "events", "-n", "gefyra"])
        _i += 1
    assert events["items"][-1]["reason"] == "Gefyra-Ready"
