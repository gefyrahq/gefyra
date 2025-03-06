import subprocess
from pathlib import Path
import os
from time import sleep
import pytest
from pytest_kubernetes.providers import AClusterManager, select_provider_manager
from pytest_kubernetes.options import ClusterOptions


@pytest.fixture(scope="session")
def carrier_image(request):
    name = "carrier2:pytest"
    subprocess.run(
        (
            f"docker build -t {name} -f"
            f" {(Path(__file__).parent / Path('../../Dockerfile')).resolve()}"
            f" {(Path(__file__).parent / Path('../../../carrier2/')).resolve()}"
        ),
        shell=True,
    )
    request.addfinalizer(lambda: subprocess.run(f"docker rmi {name}", shell=True))
    return name


@pytest.fixture(scope="session")
def demo_backend_image(request):
    name = "gefyra-demo-backend:pytest"
    subprocess.run(
        (f"docker pull quay.io/gefyra/gefyra-demo-backend"),
        shell=True,
    )
    subprocess.run(
        (f"docker tag quay.io/gefyra/gefyra-demo-backend " + name),
        shell=True,
    )
    return name


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
