from gefyra.configuration import ClientConfiguration
from pytest_kubernetes.providers import AClusterManager


def test_get_env_from_pod(k3d: AClusterManager, carrier2_image):
    from gefyra.cluster.utils import get_env_from_pod_container

    config = ClientConfiguration(
        kube_config_file=k3d.kubeconfig, kube_context=k3d.context
    )

    k3d.load_image(carrier2_image)

    k3d.apply("tests/fixtures/env_pods.yaml")
    k3d.wait(
        "pod/carrier-12",
        "condition=ready",
        namespace="default",
        timeout=60,
    )
    raw_env = get_env_from_pod_container(config, "carrier-12", "default", "carrier")
    assert "test" in raw_env
    assert "mytest" in raw_env

    k3d.wait(
        "pod/alpine",
        "condition=ready",
        namespace="default",
        timeout=60,
    )
    raw_env = get_env_from_pod_container(config, "alpine", "default", "alpine")

    assert "distro" in raw_env
    assert "alpine" in raw_env

    k3d.wait(
        "pod/python",
        "condition=ready",
        namespace="default",
        timeout=60,
    )
    raw_env = get_env_from_pod_container(config, "python", "default", "python")

    assert "distro" in raw_env
    assert "python:3-slim" in raw_env
