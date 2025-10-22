import os
from pathlib import Path
import subprocess
from time import sleep
import pytest
from pytest_kubernetes.providers import AClusterManager


@pytest.fixture(scope="session")
def demo_backend_image(request):
    name = "quay.io/gefyra/pyserver:latest"
    subprocess.run(
        ("docker pull quay.io/gefyra/pyserver:latest"),
        shell=True,
    )
    return name


@pytest.fixture(scope="module")
def k3d(k8s_manager):
    k8s: AClusterManager = k8s_manager("k3d")("gefyra")

    # check if we are running against an existing cluster
    cluster_exists = k8s.ready(timeout=1)
    if not cluster_exists:
        k8s.create(
            None,
            options=[
                '--port="31820:31820/UDP@agent:0"',
                "-p",
                "8080:80@agent:0",
                "--agents=1",
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


@pytest.fixture(scope="session")
def operator_image(request):
    name = "operator:pytest"
    subprocess.run(
        (
            f"docker build -t {name} --platform linux/amd64 -f"
            f" {(Path(__file__).parent / Path('../../operator/Dockerfile')).resolve()}"
            f" {(Path(__file__).parent / Path('../../operator/')).resolve()}"
        ),
        shell=True,
    )
    # request.addfinalizer(lambda: subprocess.run(f"docker rmi {name}", shell=True))
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


@pytest.fixture(scope="class")
def operator(request):
    if request.param:
        return request.getfixturevalue(request.param)
    else:
        return request.getfixturevalue("operator_with_sa")


@pytest.fixture(scope="module")
def operator_with_sa(k3d: AClusterManager, operator_image, stowaway_image):
    # we can omit loading images if they are already present in the cluster
    check_images_loaded(k3d, operator_image, stowaway_image)
    k3d.apply(Path(__file__).parent / Path("fixtures/operator.yaml"))

    check_operator_running(k3d)
    yield k3d


@pytest.fixture(scope="module")
def operator_no_sa(k3d: AClusterManager, operator_image, stowaway_image):
    # we can omit loading images if they are already present in the cluster
    check_images_loaded(k3d, operator_image, stowaway_image)
    k3d.apply(Path(__file__).parent / Path("fixtures/operator_no_sa.yaml"))

    check_operator_running(k3d)
    yield k3d


def check_operator_running(k3d):
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


def check_images_loaded(k3d, operator_image, stowaway_image):
    loaded_images = subprocess.check_output(
        f"docker exec k3d-{k3d.cluster_name}-server-0 crictl images", shell=True
    ).decode("utf-8")
    if "docker.io/library/operator" not in loaded_images:
        k3d.load_image(operator_image)
    if "docker.io/library/stowaway" not in loaded_images:
        k3d.load_image(stowaway_image)


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
    except RuntimeError:
        pass
