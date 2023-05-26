import json
import logging

from pytest_kubernetes.providers import AClusterManager
from .utils import GefyraDockerClient

logger = logging.getLogger(__name__)


def test_a_connect_clients(
    cargo_image,
    operator: AClusterManager,
    gclient_a: GefyraDockerClient,
    gclient_b: GefyraDockerClient,
):
    k3d = operator
    k3d.apply("tests/fixtures/a_gefyra_client.yaml")

    k3d.wait(
        "gefyraclients.gefyra.dev/client-a",
        "jsonpath=.state=WAITING",
        namespace="gefyra",
        timeout=20,
    )
    # client connect taking place
    k3d.kubectl(
        [
            "-n",
            "gefyra",
            "patch",
            "gefyraclient",
            "client-a",
            "--type='merge'",
            f"--patch='"
            + json.dumps({"providerParameter": {"subnet": "192.168.101.0/24"}})
            + "'",
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
    gclient_a.probe()
    # client disconnect taking place
    gclient_a.delete()
    k3d.kubectl(
        [
            "-n",
            "gefyra",
            "patch",
            "gefyraclient",
            "client-a",
            "--type='merge'",
            f"--patch='" + json.dumps({"providerParameter": None}) + "'",
        ]
    )
    k3d.wait(
        "gefyraclients.gefyra.dev/client-a",
        "jsonpath=.state=WAITING",
        namespace="gefyra",
        timeout=20,
    )
    k3d.apply("tests/fixtures/b_gefyra_client.yaml")
    k3d.wait(
        "gefyraclients.gefyra.dev/client-b",
        "jsonpath=.state=WAITING",
        namespace="gefyra",
        timeout=20,
    )
    k3d.kubectl(
        [
            "-n",
            "gefyra",
            "patch",
            "gefyraclient",
            "client-a",
            "--type='merge'",
            "--patch='"
            + json.dumps({"providerParameter": {"subnet": "192.168.102.0/24"}})
            + "'",
        ]
    )
    k3d.kubectl(
        [
            "-n",
            "gefyra",
            "patch",
            "gefyraclient",
            "client-b",
            "--type='merge'",
            f"--patch='"
            + json.dumps({"providerParameter": {"subnet": "192.168.103.0/24"}})
            + "'",
        ]
    )
    k3d.wait(
        "gefyraclients.gefyra.dev/client-a",
        "jsonpath=.state=ACTIVE",
        namespace="gefyra",
        timeout=20,
    )
    k3d.wait(
        "gefyraclients.gefyra.dev/client-b",
        "jsonpath=.state=ACTIVE",
        namespace="gefyra",
        timeout=20,
    )
    client_a = k3d.kubectl(
        ["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"]
    )

    client_b = k3d.kubectl(
        ["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-b"]
    )

    gclient_a.connect(client_a["providerConfig"])
    gclient_a.probe()
    gclient_b.connect(client_b["providerConfig"])
    gclient_b.probe()
    gclient_a.delete()
    gclient_b.delete()
