from time import sleep
from pytest_kubernetes.providers import AClusterManager


def test_a_run_pod(k3d: AClusterManager, carrier_image):

    k3d.load_image(carrier_image)

    k3d.apply("tests/fixtures/carrier2_pod.yaml")
    k3d.wait(
        "pod/carrier-1000",
        "condition=ready",
        namespace="default",
        timeout=60,
    )
    k3d.wait(
        "pod/carrier-500",
        "condition=ready",
        namespace="default",
        timeout=60,
    )
    k3d.wait(
        "pod/carrier-nosec",
        "condition=ready",
        namespace="default",
        timeout=60,
    )
    k3d.wait(
        "pod/carrier-cmd",
        "condition=ready",
        namespace="default",
        timeout=60,
    )
    # give k8s time to detect and restart a faulty container
    sleep(5)
    for pod in [
        "pod/carrier-cmd",
        "pod/carrier-1000",
        "pod/carrier-500",
        "pod/carrier-nosec",
    ]:
        pod = k3d.kubectl(["get", pod])
        assert pod["status"]["containerStatuses"][0]["ready"] == True
        assert pod["status"]["containerStatuses"][0]["restartCount"] == 0


def test_b_patch_carrier(k3d: AClusterManager, carrier_image, demo_backend_image):

    k3d.load_image(demo_backend_image)
    k3d.load_image(carrier_image)

    import kubernetes

    kubernetes.config.load_kube_config(config_file=str(k3d.kubeconfig))

    from kubernetes.client.api import core_v1_api

    core_v1 = core_v1_api.CoreV1Api()

    k3d.kubectl(["create", "namespace", "demo"])
    k3d.wait("ns/demo", "jsonpath='{.status.phase}'=Active")
    k3d.apply("tests/fixtures/demo_pods.yaml")

    k3d.wait(
        "pod/backend",
        "condition=ready",
        namespace="demo",
        timeout=60,
    )

    # this is a core of the patch operation
    pod = core_v1.read_namespaced_pod(name="backend", namespace="demo")
    pod.spec.containers[0].image = carrier_image
    core_v1.patch_namespaced_pod(name="backend", namespace="demo", body=pod)

    backend_pod = k3d.kubectl(["get", "pod", "backend", "-n", "demo"])
    assert backend_pod["spec"]["containers"][0]["image"] == carrier_image

    k3d.wait(
        "pod/backend",
        "jsonpath='{.status.containerStatuses[0].image}'=docker.io/library/"
        + carrier_image,
        namespace="demo",
        timeout=60,
    )
    k3d.wait(
        "pod/backend",
        "condition=ready",
        namespace="demo",
        timeout=60,
    )

    backend_pod = k3d.kubectl(["get", "pod", "backend", "-n", "demo"])
    assert backend_pod["spec"]["containers"][0]["image"] == carrier_image
    assert backend_pod["status"]["containerStatuses"][0]["ready"] == True
    assert backend_pod["status"]["containerStatuses"][0]["restartCount"] == 1
