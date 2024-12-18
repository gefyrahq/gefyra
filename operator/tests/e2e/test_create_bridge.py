import json
import logging
from pytest_kubernetes.providers import AClusterManager
from .utils import GefyraDockerClient

logger = logging.getLogger(__name__)


def test_a_bridge(
    demo_backend_image,
    demo_frontend_image,
    carrier_image,
    operator: AClusterManager,
    gclient_a: GefyraDockerClient,
):
    k3d = operator
    k3d.load_image(demo_backend_image)
    k3d.load_image(demo_frontend_image)
    k3d.load_image(carrier_image)

    k3d.kubectl(["create", "namespace", "demo"])
    k3d.wait("ns/demo", "jsonpath='{.status.phase}'=Active")
    k3d.apply("tests/fixtures/demo_pods.yaml")
    k3d.wait(
        "pod/backend",
        "condition=ready",
        namespace="demo",
        timeout=60,
    )

    k3d.apply("tests/fixtures/a_gefyra_client.yaml")

    k3d.wait(
        "gefyraclients.gefyra.dev/client-a",
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

    k3d.apply("tests/fixtures/a_gefyra_bridge.yaml")
    k3d.wait(
        "gefyrabridges.gefyra.dev/bridge-a",
        "jsonpath=.state=ACTIVE",
        namespace="gefyra",
        timeout=20,
    )
    k3d.wait(
        "pod/backend",
        "jsonpath=.status.containerStatuses[0].image=docker.io/library/"
        + carrier_image,
        namespace="demo",
        timeout=60,
    )
    k3d.wait(
        "pod/backend",
        "condition=ready",
        namespace="demo",
        timeout=10,
    )

    k3d.kubectl(
        ["-n", "gefyra", "exec", "gefyra-stowaway-0", "--", "nginx", "-s", "reload"],
        as_dict=False,
    )
    k3d.kubectl(
        ["-n", "gefyra", "delete", "-f", "tests/fixtures/a_gefyra_bridge.yaml"],
        as_dict=False,
    )
    k3d.wait(
        "pod/backend",
        "jsonpath=.status.containerStatuses[0].image=quay.io/gefyra/gefyra-demo-backend:latest",
        namespace="demo",
        timeout=60,
    )

    gclient_a.delete()


def test_b_cleanup_bridges_routes(
    carrier_image,
    operator: AClusterManager,
):
    k3d = operator

    k3d.apply("tests/fixtures/a_gefyra_bridge.yaml")
    k3d.wait(
        "gefyrabridges.gefyra.dev/bridge-a",
        "jsonpath=.state=ACTIVE",
        namespace="gefyra",
        timeout=20,
    )
    k3d.wait(
        "pod/backend",
        "jsonpath=.status.containerStatuses[0].image=docker.io/library/"
        + carrier_image,
        namespace="demo",
        timeout=60,
    )
    k3d.kubectl(
        ["-n", "gefyra", "delete", "gefyraclients.gefyra.dev", "client-a"],
        as_dict=False,
    )
    k3d.wait(
        "gefyrabridges.gefyra.dev/bridge-a",
        "delete",
        namespace="gefyra",
        timeout=60,
    )


def test_c_fail_create_not_supported_bridges(
    demo_backend_image, demo_frontend_image, carrier_image, operator: AClusterManager
):
    k3d = operator
    k3d.load_image(demo_backend_image)
    k3d.load_image(demo_frontend_image)
    k3d.load_image(carrier_image)

    k3d.kubectl(["create", "namespace", "demo-failing"])
    k3d.wait("ns/demo-failing", "jsonpath='{.status.phase}'=Active")
    k3d.apply("tests/fixtures/demo_pods_not_supported.yaml")
    k3d.wait(
        "pod/frontend",
        "condition=ready",
        namespace="demo-failing",
        timeout=60,
    )

    k3d.apply("tests/fixtures/a_gefyra_bridge_failing.yaml")
    # bridge should be in error state
    k3d.wait(
        "gefyrabridges.gefyra.dev/bridge-a",
        "jsonpath=.state=ERROR",
        namespace="gefyra",
        timeout=20,
    )

    # applying the bridge shouldn't have worked
    k3d.wait(
        "pod/frontend",
        "condition=ready",
        namespace="demo-failing",
        timeout=60,
    )
