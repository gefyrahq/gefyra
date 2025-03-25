from pytest_kubernetes.providers import AClusterManager


def test_a_create_bridge_mount(operator: AClusterManager):
    k3d = operator
    k3d.apply("tests/fixtures/nginx.yaml")
    k3d.apply("tests/fixtures/bridge_mount.yaml")

    k3d.wait(
        "gefyrabridgemounts.gefyra.dev/bridgemount-a",
        "jsonpath=.state=REQUESTED",
        namespace="gefyra",
        timeout=40,
    )
    k3d.wait(
        "gefyrabridgemounts.gefyra.dev/bridgemount-a",
        "jsonpath=.state=ACTIVE",
        namespace="gefyra",
        timeout=120,
    )
    bridge_mount_obj = k3d.kubectl(
        ["-n", "gefyra", "get", "gefyrabridgemounts.gefyra.dev", "bridgemount-a"]
    )
    assert bridge_mount_obj["state"] == "ACTIVE"

    k3d.wait(
        "deployment/nginx-deployment-gefyra",
        "jsonpath='{.status.readyReplicas}'=1",
        namespace="default",
        timeout=60,
    )
    pod = k3d.kubectl(["-n", "default", "get", "pod", "-l", "app=nginx", "-o", "json"])
    assert (
        pod["items"][0]["spec"]["containers"][0]["image"]
        == "quay.io/gefyra/carrier2:test"  # TODO change to latest
    )

    k3d.apply("tests/fixtures/a_gefyra_bridge_carrier2.yaml")
    k3d.wait(
        "gefyrabridges.gefyra.dev/bridge-a",
        "jsonpath=.state=ACTIVE",
        namespace="gefyra",
        timeout=120,
    )
    # todo fetch config from container
    # check if config is correct
