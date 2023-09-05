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
