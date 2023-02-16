from pytest_kubernetes.providers import AClusterManager

def test_a_run_operator(operator):
    operator, k8s = operator
    namespaces = k8s.kubectl(["get", "ns"], as_dict=False)
    print(namespaces)