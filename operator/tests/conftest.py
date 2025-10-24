import logging
import os
import platform
import sys
from pathlib import Path
import subprocess
from time import sleep
import pytest
from pytest_kubernetes.providers import AClusterManager
from pytest_kubernetes.options import ClusterOptions

from tests.utils import GefyraDockerClient


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
def k3d(k8s_manager):
    k8s: AClusterManager = k8s_manager("k3d")("gefyra")
    # ClusterOptions() forces pytest-kubernetes to always write a new kubeconfig file to disk
    cluster_exists = k8s.ready(timeout=1)
    if not cluster_exists:
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
    if "gefyra" not in k8s.kubectl(["get", "ns"], as_dict=False):
        k8s.kubectl(["create", "ns", "gefyra"])
        k8s.wait("ns/gefyra", "jsonpath='{.status.phase}'=Active")
    else:
        purge_gefyra_objects(k8s)
    os.environ["KUBECONFIG"] = str(k8s.kubeconfig)
    print(f"This test run's kubeconfig location: {k8s.kubeconfig}")
    yield k8s
    if cluster_exists:
        # delete existing bridges
        purge_gefyra_objects(k8s)
        k8s.kubectl(["delete", "ns", "gefyra"], as_dict=False)
    else:
        # we delete this cluster only when created during this run
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
def short_env():
    os.environ["GEFYRA_STOWAWAY_MAX_CONNECTION_AGE"] = "5"


@pytest.fixture(scope="module")
def operator(k3d, stowaway_image, carrier_image):
    from kopf.testing import KopfRunner

    os.environ["GEFYRA_STOWAWAY_IMAGE"] = stowaway_image.split(":")[0]
    os.environ["GEFYRA_STOWAWAY_TAG"] = stowaway_image.split(":")[1]
    os.environ["GEFYRA_STOWAWAY_IMAGE_PULLPOLICY"] = "Never"
    os.environ["GEFYRA_CARRIER_IMAGE"] = carrier_image.split(":")[0]
    os.environ["GEFYRA_CARRIER_IMAGE_TAG"] = carrier_image.split(":")[1]
    os.environ["GEFYRA_CARRIER2_DEBUG"] = "True"
    loaded_images = subprocess.check_output(
        f"docker exec k3d-{k3d.cluster_name}-server-0 crictl images", shell=True
    ).decode("utf-8")
    if "docker.io/library/stowaway" not in loaded_images:
        k3d.load_image(stowaway_image)
    operator = KopfRunner(["run", "-A", "--dev", "main.py"])
    operator.__enter__()
    kopf_logger = logging.getLogger("kopf")
    kopf_logger.setLevel(logging.INFO)
    gefyra_logger = logging.getLogger("gefyra")
    gefyra_logger.setLevel(logging.INFO)
    purge_gefyra_objects(k3d)

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
    purge_gefyra_objects(k3d)
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
    # request.addfinalizer(lambda: subprocess.run(f"docker rmi {name}", shell=True))
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
    # request.addfinalizer(lambda: subprocess.run(f"docker rmi {name}", shell=True))
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
    # request.addfinalizer(lambda: subprocess.run(f"docker rmi {name}", shell=True))
    return name


@pytest.fixture(scope="session")
def carrier2_image(request):
    name = "carrier2:pytest"
    subprocess.run(
        (
            f"docker build -t {name} -f"
            f" {(Path(__file__).parent / Path('../../carrier2/Dockerfile')).resolve()}"
            f" {(Path(__file__).parent / Path('../../carrier2/')).resolve()}"
        ),
        shell=True,
    )
    # request.addfinalizer(lambda: subprocess.run(f"docker rmi {name}", shell=True))
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


@pytest.fixture(scope="session")
def cargo_image(request):
    name = "cargo:pytest"
    if sys.platform == "win32" or "microsoft-standard" in platform.release():
        target = "cargo-win"
    else:
        target = "cargo"
    subprocess.run(
        (
            f"docker build --target {target} -t {name} -f"
            f" {(Path(__file__).parent / Path('../../cargo/Dockerfile')).resolve()}"
            f" {(Path(__file__).parent / Path('../../cargo/')).resolve()}"
        ),
        shell=True,
    )
    # request.addfinalizer(lambda: subprocess.run(f"docker rmi {name}", shell=True))
    return name


@pytest.fixture(scope="session")
def gclient_a(cargo_image):
    c = GefyraDockerClient("gclient-a")
    yield c
    try:
        c.delete()
    except Exception:
        pass


@pytest.fixture(scope="session")
def gclient_b():
    c = GefyraDockerClient("gclient-b")
    yield c
    try:
        c.delete()
    except Exception:
        pass


def purge_gefyra_objects(k8s):
    # delete existing bridges
    try:
        # delete existing bridges
        bridges = k8s.kubectl(
            [
                "-n",
                "gefyra",
                "get",
                "gefyrabridges",
                "-o",
                "jsonpath='{.items[*].metadata.name}'",
            ],
            as_dict=False,
        ).split("\n")
        for bridge in bridges:
            if bridge and "No resources" not in bridge:
                k8s.kubectl(
                    ["-n", "gefyra", "delete", "gefyrabridge", bridge], as_dict=False
                )
    except RuntimeError:
        pass
    # delete existing bridge mounts
    try:
        mounts = k8s.kubectl(
            [
                "-n",
                "gefyra",
                "get",
                "gefyrabridgemounts",
                "-o",
                "jsonpath='{.items[*].metadata.name}'",
            ],
            as_dict=False,
        ).split("\n")
        for mount in mounts:
            if mount and "No resources" not in mount:
                k8s.kubectl(
                    ["-n", "gefyra", "delete", "gefyrabridgemount", mount],
                    as_dict=False,
                )
    except RuntimeError:
        pass
    # delete existing clients
    try:
        clients = k8s.kubectl(
            [
                "-n",
                "gefyra",
                "get",
                "gefyraclients",
                "-o",
                "jsonpath='{.items[*].metadata.name}'",
            ],
            as_dict=False,
        ).split("\n")
        for client in clients:
            if client and "No resources" not in client:
                k8s.kubectl(
                    ["-n", "gefyra", "delete", "gefyraclient", client], as_dict=False
                )
    except (RuntimeError, subprocess.TimeoutExpired):
        pass
