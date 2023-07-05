from gefyra.cluster.utils import get_v1pod
from gefyra.configuration import ClientConfiguration
from pytest_kubernetes.providers import AClusterManager


def test_get_v1_pod(k3d: AClusterManager):
    config = ClientConfiguration(
        kube_config_file=k3d.kubeconfig, kube_context=k3d.context
    )
    k3d.kubectl(["create", "namespace", "demo"])
    k3d.wait("ns/demo", "jsonpath='{.status.phase}'=Active")
    k3d.apply("tests/fixtures/demo_pods.yaml")
    k3d.wait(
        "pod/backend",
        "condition=ready",
        namespace="demo",
        timeout=60,
    )
    pod = get_v1pod(config=config, namespace="demo", pod_name="backend")
    assert pod.metadata.name == "backend"
    try:
        get_v1pod(config=config, pod_name="blah", namespace="demo")
    except RuntimeError as rte:
        assert "does not exist" in str(rte)
