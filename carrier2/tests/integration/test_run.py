from time import sleep
from pytest_kubernetes.providers import AClusterManager
import requests
from requests.adapters import HTTPAdapter, Retry
import tempfile

import utils


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
        "pod/carrier-12",
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
        "pod/carrier-12",
        "pod/carrier-nosec",
    ]:
        pod = k3d.kubectl(["get", pod])
        assert pod["status"]["containerStatuses"][0]["ready"] == True
        assert pod["status"]["containerStatuses"][0]["restartCount"] == 0


def test_b_patch_carrier(k3d: AClusterManager, carrier_image, demo_backend_image):

    k3d.load_image(demo_backend_image)

    retries = Retry(total=5, backoff_factor=0.2)
    session = requests.Session()
    session.mount("http://localhost:8091", HTTPAdapter(max_retries=retries))

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
    # get k8s some time to pick up the endpoint
    sleep(5)

    # test ingress from demo workload
    resp = session.get("http://localhost:8091/color")
    assert resp.status_code == 200
    assert "blue" in resp.text  # { "color": "blue" }

    # -- this is a core of the patch operation --
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
    sleep(5)

    backend_pod = k3d.kubectl(["get", "pod", "backend", "-n", "demo"])
    assert backend_pod["spec"]["containers"][0]["image"] == carrier_image
    assert backend_pod["status"]["containerStatuses"][0]["ready"] == True
    assert backend_pod["status"]["containerStatuses"][0]["restartCount"] == 1
    # -- end patch operation --

    # the demo workload is not serving anymore, we expect a 502
    resp = requests.get("http://localhost:8091/color")
    assert resp.status_code == 502


def test_c_configure_cluster_upstream(k3d: AClusterManager):
    import textwrap

    content = textwrap.dedent(
        """
    ---
    version: 1
    threads: 4
    pid_file: /tmp/carrier2.pid
    error_log: /tmp/carrier.error.log
    upgrade_sock: /tmp/carrier2.sock
    upstream_keepalive_pool_size: 100
    port: 5002
    clusterUpstream: 
        - \"{ip}:5002\"
    """
    )

    shadow_pod = k3d.kubectl(["get", "pod", "backend-shadow", "-n", "demo"])
    pod_ip = shadow_pod["status"]["podIP"]

    content_str = content.format(ip=pod_ip)

    from kubernetes.client.api import core_v1_api

    core_v1 = core_v1_api.CoreV1Api()

    utils.send_carrier2_config(core_v1, "backend", "demo", content_str)
    utils.reload_carrier2_config(core_v1, "backend", "demo")

    retries = Retry(total=5, backoff_factor=0.2)
    session = requests.Session()
    session.mount("http://localhost:8091", HTTPAdapter(max_retries=retries))

    # the is now served from backend-shadow (from the cluster) via Carrier2
    resp = session.get("http://localhost:8091/color")
    assert resp.status_code == 200
    assert "blue" in resp.text  # { "color": "blue" }
