import logging
import os
import sys
from pathlib import Path
import subprocess
from time import sleep
import pytest
from pytest_kubernetes.providers import AClusterManager, select_provider_manager
from pytest_kubernetes.options import ClusterOptions


@pytest.fixture(autouse=True, scope="module")
def reload_kubernetes():
    for key in list(sys.modules.keys()):
        if (
            key.startswith("kubernetes")
            or key.startswith("k8s")
            or key.startswith("gefyra")
        ):
            del sys.modules[key]


@pytest.fixture(scope="module")
def k3d():
    k8s: AClusterManager = select_provider_manager("k3d")("gefyra")
    # ClusterOptions() forces pytest-kubernetes to always write a new kubeconfig file to disk
    k8s.create(
        ClusterOptions(api_version="1.29.5"),
        options=[
            "--agents",
            "1",
            "-p",
            "8080:80@agent:0",
            "-p",
            "31820:31820/UDP@agent:0",
            "--agents-memory",
            "8G",
        ],
    )
    k8s.kubectl(["create", "ns", "gefyra"])
    k8s.wait("ns/gefyra", "jsonpath='{.status.phase}'=Active")
    os.environ["KUBECONFIG"] = str(k8s.kubeconfig)
    print(f"This test run's kubeconfig location: {k8s.kubeconfig}")
    yield k8s
    k8s.delete()
    timeout = 0
    exited = False
    while not exited and timeout < 60:
        try:
            k8s._exec(["cluster", "get", k8s.cluster_name], timeout=5)
        except subprocess.CalledProcessError:
            exited = True
        timeout += 1
        sleep(1)
    if not exited:
        raise Exception("K3d cluster did not exit")


@pytest.fixture(scope="module")
def operator(k3d, stowaway_image, carrier_image):
    from kopf.testing import KopfRunner

    os.environ["GEFYRA_STOWAWAY_IMAGE"] = stowaway_image.split(":")[0]
    os.environ["GEFYRA_STOWAWAY_TAG"] = stowaway_image.split(":")[1]
    os.environ["GEFYRA_STOWAWAY_IMAGE_PULLPOLICY"] = "Never"
    os.environ["GEFYRA_CARRIER_IMAGE"] = carrier_image.split(":")[0]
    os.environ["GEFYRA_CARRIER_IMAGE_TAG"] = carrier_image.split(":")[1]
    k3d.load_image(stowaway_image)
    operator = KopfRunner(["run", "-A", "--dev", "main.py"])
    operator.__enter__()
    kopf_logger = logging.getLogger("kopf")
    kopf_logger.setLevel(logging.INFO)
    gefyra_logger = logging.getLogger("gefyra")
    gefyra_logger.setLevel(logging.INFO)

    not_found = True
    _i = 0
    try:
        while not_found and _i < 190:
            sleep(1)
            events = k3d.kubectl(["get", "events", "-n", "gefyra"])
            _i += 1
            for event in events["items"]:
                if event["reason"] == "Gefyra-Ready":
                    not_found = False
    except Exception:
        operator.timeout = 10
        operator.__exit__(None, None, None)
    if not_found:
        operator.timeout = 10
        operator.__exit__(None, None, None)
        raise Exception("Gefyra-Ready event not found")

    yield k3d
    for key in list(sys.modules.keys()):
        if key.startswith("kopf"):
            del sys.modules[key]
    operator.timeout = 10
    operator.__exit__(None, None, None)


@pytest.fixture(scope="session")
def stowaway_image(request):
    name = "stowaway:pytest"
    subprocess.run(
        (
            f"docker build -t {name} -f"
            f" {(Path(__file__).parent / Path('../../stowaway/Dockerfile')).resolve()}"
            f" {(Path(__file__).parent / Path('../../stowaway/')).resolve()}"
        ),
        shell=True,
    )
    request.addfinalizer(lambda: subprocess.run(f"docker rmi {name}", shell=True))
    return name


@pytest.fixture(scope="session")
def operator_image(request):
    name = "operator:pytest"
    subprocess.run(
        (
            f"docker build -t {name} -f"
            f" {(Path(__file__).parent / Path('../Dockerfile')).resolve()}"
            f" {(Path(__file__).parent / Path('../')).resolve()}"
        ),
        shell=True,
    )
    request.addfinalizer(lambda: subprocess.run(f"docker rmi {name}", shell=True))
    return name


@pytest.fixture(scope="session")
def carrier_image(request):
    name = "carrier:pytest"
    subprocess.run(
        (
            f"docker build -t {name} -f"
            f" {(Path(__file__).parent / Path('../../carrier/Dockerfile')).resolve()}"
            f" {(Path(__file__).parent / Path('../../carrier/')).resolve()}"
        ),
        shell=True,
    )
    request.addfinalizer(lambda: subprocess.run(f"docker rmi {name}", shell=True))
    return name


@pytest.fixture(scope="module")
def gefyra_crd(k3d):
    import kubernetes

    kubernetes.config.load_kube_config(config_file=str(k3d.kubeconfig))
    from gefyra.handler.startup import handle_crds

    logger = logging.getLogger()
    handle_crds(logger)

    yield k3d


@pytest.fixture(scope="session")
def demo_backend_image():
    name = "quay.io/gefyra/gefyra-demo-backend"
    subprocess.run(
        f"docker pull {name}",
        shell=True,
    )
    yield name


@pytest.fixture(scope="session")
def demo_frontend_image():
    name = "quay.io/gefyra/gefyra-demo-frontend"
    subprocess.run(
        f"docker pull {name}",
        shell=True,
    )
    yield name
