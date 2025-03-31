from gefyra.cluster.utils import (
    get_env_from_pod_container,
    get_v1pod,
    retrieve_pod_and_container,
)
from gefyra.configuration import ClientConfiguration
from pytest_kubernetes.providers import AClusterManager


# def test_get_v1_pod(k3d: AClusterManager):
#     config = ClientConfiguration(
#         kube_config_file=k3d.kubeconfig, kube_context=k3d.context
#     )
#     k3d.kubectl(["create", "namespace", "demo"])
#     k3d.wait("ns/demo", "jsonpath='{.status.phase}'=Active")
#     k3d.apply("tests/fixtures/demo_pods.yaml")
#     k3d.wait(
#         "pod/backend",
#         "condition=ready",
#         namespace="demo",
#         timeout=60,
#     )
#     pod = get_v1pod(config=config, namespace="demo", pod_name="backend")
#     assert pod.metadata.name == "backend"
#     try:
#         get_v1pod(config=config, pod_name="blah", namespace="demo")
#     except RuntimeError as rte:
#         assert "does not exist" in str(rte)


# def test_retrieve_pod_and_container(k3d: AClusterManager):
#     config = ClientConfiguration(
#         kube_config_file=k3d.kubeconfig, kube_context=k3d.context
#     )
#     assert ("backend", "backend") == retrieve_pod_and_container(
#         "pod/backend/backend", namespace="demo", config=config
#     )

#     try:
#         retrieve_pod_and_container(
#             "pod/backend/random", namespace="demo", config=config
#         )
#     except Exception as e:
#         assert "was not found for" in str(e)


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
    from time import sleep

    assert "distro" in raw_env
    assert "alpine" in raw_env

    k3d.wait(
        "pod/python",
        "condition=ready",
        namespace="default",
        timeout=60,
    )
    raw_env = get_env_from_pod_container(config, "python", "default", "python")
    from time import sleep

    assert "distro" in raw_env
    assert "python:3-slim" in raw_env
