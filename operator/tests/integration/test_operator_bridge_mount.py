from pytest_kubernetes.providers import AClusterManager


def test_a_create_bridge_mount(operator: AClusterManager):
    k3d = operator
    k3d.apply("tests/fixtures/nginx.yaml")
    k3d.wait(
        "deployment/nginx-deployment",
        "jsonpath='{.status.readyReplicas}'=1",
        namespace="default",
        timeout=120,
    )

    k3d.apply("tests/fixtures/bridge_mount.yaml")

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
        == "quay.io/gefyra/carrier2:latest"
    )


def test_b_change_deployment_replicas(operator: AClusterManager):
    k3d = operator
    k3d.kubectl(
        [
            "-n",
            "default",
            "scale",
            "deployment/nginx-deployment",
            "--replicas=2",
        ],
        as_dict=False,
    )
    k3d.wait(
        "deployment/nginx-deployment",
        "jsonpath='{.status.readyReplicas}'=2",
        namespace="default",
        timeout=120,
    )
    # Operator recognizes the change and restores the bridge mount.
    # Wait for ACTIVE directly — RESTORING is near-instantaneous because
    # on_restore() immediately calls self.send("prepare").
    k3d.wait(
        "gefyrabridgemounts.gefyra.dev/bridgemount-a",
        "jsonpath=.state=ACTIVE",
        namespace="gefyra",
        timeout=120,
    )
    # Verify the restoration cycle occurred via stateTransitions
    bridge_mount_obj = k3d.kubectl(
        ["-n", "gefyra", "get", "gefyrabridgemounts.gefyra.dev", "bridgemount-a"]
    )
    transitions = bridge_mount_obj.get("stateTransitions", {})
    assert "RESTORING" in transitions, (
        "Expected RESTORING state transition after replica change"
    )
    pod = k3d.kubectl(["-n", "default", "get", "pod", "-l", "app=nginx", "-o", "json"])
    assert (
        pod["items"][0]["spec"]["containers"][0]["image"]
        == "quay.io/gefyra/carrier2:latest"
    )
    assert (
        pod["items"][1]["spec"]["containers"][0]["image"]
        == "quay.io/gefyra/carrier2:latest"
    )


def test_c_bridge_mount_terminate(operator: AClusterManager):
    k3d = operator
    k3d.kubectl(
        [
            "-n",
            "gefyra",
            "delete",
            "gefyrabridgemounts.gefyra.dev",
            "bridgemount-a",
        ],
        as_dict=False,
    )

    k3d.wait(
        "gefyrabridgemounts.gefyra.dev/bridgemount-a",
        "delete",
        namespace="gefyra",
        timeout=20,
    )
