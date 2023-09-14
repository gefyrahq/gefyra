import os
from pathlib import Path
import subprocess
from time import sleep
import pytest
from pytest_kubernetes.providers import AClusterManager, select_provider_manager
from pytest_kubernetes.options import ClusterOptions


@pytest.fixture(scope="module")
def k3d():
    k8s: AClusterManager = select_provider_manager("k3d")("gefyra")
    # ClusterOptions() forces pytest-kubernetes to always write a new kubeconfig file to disk
    k8s.create(ClusterOptions())
    k8s.kubectl(["create", "ns", "gefyra"])
    k8s.wait("ns/gefyra", "jsonpath='{.status.phase}'=Active")
    os.environ["KUBECONFIG"] = str(k8s.kubeconfig)
    print(f"This test run's kubeconfig location: {k8s.kubeconfig}")
    yield k8s
    k8s.delete()


@pytest.fixture(scope="session")
def operator_image(request):
    name = "operator:pytest"
    subprocess.run(
        (
            f"docker build -t {name} -f"
            f" {(Path(__file__).parent / Path('../../operator/Dockerfile')).resolve()}"
            f" {(Path(__file__).parent / Path('../../operator/')).resolve()}"
        ),
        shell=True,
    )
    request.addfinalizer(lambda: subprocess.run(f"docker rmi {name}", shell=True))
    return name


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


@pytest.fixture(scope="module")
def operator(k3d: AClusterManager, operator_image, stowaway_image):
    k3d.load_image(operator_image)
    k3d.load_image(stowaway_image)
    k3d.apply(Path(__file__).parent / Path("fixtures/operator.yaml"))

    not_found = True
    _i = 0
    while not_found and _i < 120:
        sleep(1)
        events = k3d.kubectl(["get", "events", "-n", "gefyra"])
        _i += 1
        for event in events["items"]:
            if event["reason"] == "Gefyra-Ready":
                not_found = False
    if not_found:
        try:
            print(
                k3d.kubectl(
                    ["describe", "deployment", "-n", "gefyra", "gefyra-operator"],
                    as_dict=False,
                )
            )
            print(
                k3d.kubectl(
                    ["logs", "-n", "gefyra", "deployment", "gefyra-operator"],
                    as_dict=False,
                )
            )
            print(
                k3d.kubectl(
                    ["logs", "-n", "gefyra", "deployment", "gefyra-operator-webhook"],
                    as_dict=False,
                )
            )
        except Exception as e:
            print(e)
        raise Exception("Gefyra-Ready event not found")
    yield k3d
