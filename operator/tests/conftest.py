import logging
import os
from pathlib import Path
import subprocess
import threading
from time import sleep
import pytest
from pytest_kubernetes.providers import AClusterManager, select_provider_manager


@pytest.fixture(scope="module")
def k3d():
    k8s: AClusterManager = select_provider_manager("k3d")("gefyra")
    k8s.create()
    k8s.kubectl(["create", "ns", "gefyra"])
    k8s.wait("ns/gefyra", "jsonpath='{.status.phase}'=Active")
    os.environ["KUBECONFIG"] = str(k8s.kubeconfig)
    yield k8s
    k8s.delete()


@pytest.fixture(scope="module")
def operator(k3d):
    import sys
    try:
        sys.modules.pop("kubernetes")
    except:
        pass
    
    from kopf.testing import KopfRunner
    import kubernetes
    kubernetes.config.load_kube_config(config_file=str(k3d.kubeconfig))


    operator = KopfRunner(["run", "-A", "main.py"])
    operator._thread.daemon = True
    operator.__enter__()
    kopf_logger = logging.getLogger("kopf")
    kopf_logger.setLevel(logging.INFO)
    gefyra_logger = logging.getLogger("gefyra")
    gefyra_logger.setLevel(logging.INFO)
    
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
        raise Exception("Gefyra-Ready event not found")
    
    yield k3d
    try:
        operator.timeout = 1
        operator.__exit__(None, None, None)
    except:
        pass


@pytest.fixture(scope="session")
def stowaway_image(request):
    name = "stowaway:pytest"
    subprocess.run(
        f"docker build -t {name} -f {(Path(__file__).parent / Path('../../stowaway/Dockerfile')).resolve()}"
        f" {(Path(__file__).parent / Path('../../stowaway/')).resolve()}",
        shell=True,
    )
    request.addfinalizer(lambda: subprocess.run(f"docker rmi {name}", shell=True))
    return name


@pytest.fixture(scope="session")
def operator_image(request):
    name = "operator:pytest"
    subprocess.run(
        f"docker build -t {name} -f {(Path(__file__).parent / Path('../Dockerfile')).resolve()}"
        f" {(Path(__file__).parent / Path('../')).resolve()}",
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

