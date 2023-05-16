import json
import logging
from time import sleep
import pytest 

from pytest_kubernetes.providers import AClusterManager
from .utils import GefyraDockerClient

logger = logging.getLogger(__name__)

@pytest.fixture(scope="session")
def gclient_a():
    
    c = GefyraDockerClient("gclient-a")
    yield c
    try:
        c.disconnect()
    except:
        pass


def test_a_connect_client_a(operator: AClusterManager, gclient_a: GefyraDockerClient):	
    k3d = operator
    k3d.apply("tests/fixtures/a_gefyra_client.yaml")

    k3d.wait(
        "gefyraclients.gefyra.dev/client-a",
        "jsonpath=.state=WAITING",
        namespace="gefyra",
        timeout=20,
    )
    patch = json.dumps({"providerParameter": {"subnet": "192.168.101.0/24"}})
    k3d.kubectl(
        [
            "-n",
            "gefyra",
            "patch",
            "gefyraclient",
            "client-a",
            "--type='merge'",
            f"--patch='{patch}'",
        ]
    )
    k3d.wait(
        "gefyraclients.gefyra.dev/client-a",
        "jsonpath=.state=ACTIVE",
        namespace="gefyra",
        timeout=20,
    )
    client_a = k3d.kubectl(
        ["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"]
    )
    assert client_a["providerConfig"] is not None
    logger.info(client_a["providerConfig"])
    gclient_a.connect(client_a["providerConfig"])
    sleep(240)
    gclient_a.probe()
    gclient_a.disconnect()

