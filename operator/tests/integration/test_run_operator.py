from time import sleep
from pytest_kubernetes.providers import AClusterManager


def test_a_boot_operator(operator: AClusterManager):
    k8s = operator
    namespaces = k8s.kubectl(["get", "ns"], as_dict=False)
    assert "gefyra" in namespaces
    sts = k8s.kubectl(["get", "statefulset", "-n", "gefyra"])

    assert len(sts["items"]) == 1
    assert sts["items"][0]["metadata"]["name"] == "gefyra-stowaway"
    k8s.wait(
        "pod/gefyra-stowaway-0",
        "condition=ready",
        namespace="gefyra",
        timeout=90,
    )
    events = k8s.kubectl(["get", "events", "-n", "gefyra"])
    not_found = True
    _i = 0
    while not_found and _i < 30:
        sleep(1)
        events = k8s.kubectl(["get", "events", "-n", "gefyra"])
        _i += 1
        for event in events["items"]:
            if event["reason"] == "Gefyra-Ready":
                not_found = False
    if not_found:
        raise Exception("Gefyra operator did not become ready")
