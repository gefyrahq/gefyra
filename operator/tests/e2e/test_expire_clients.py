from datetime import datetime, timedelta
import json
from pytest_kubernetes.providers import AClusterManager


def test_a_expire_client(
    operator: AClusterManager,
):
    k3d = operator
    k3d.apply("tests/fixtures/a_gefyra_client.yaml")
    _timeout = f"{datetime.utcnow() + timedelta(seconds=10)}Z"
    k3d.kubectl(
        [
            "-n",
            "gefyra",
            "patch",
            "gefyraclient",
            "client-a",
            "--type='merge'",
            "--patch='" + json.dumps({"sunset": _timeout}) + "'",
        ]
    )
    k3d.wait(
        "gefyraclients.gefyra.dev/client-a",
        "jsonpath=.state=WAITING",
        namespace="gefyra",
        timeout=20,
    )
    client = k3d.kubectl(
        ["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"]
    )
    assert client["sunset"] == _timeout
    k3d.wait(
        "gefyraclients.gefyra.dev/client-a",
        "delete",
        namespace="gefyra",
        timeout=20,
    )
