import json
from datetime import datetime, timedelta, timezone

from pytest_kubernetes.providers import AClusterManager


def test_a_expire_client(
    operator: AClusterManager,
):
    k3d = operator
    k3d.apply("tests/fixtures/a_gefyra_client.yaml")
    _timeout = (
        (datetime.now(timezone.utc) + timedelta(seconds=10))
        .isoformat()
        .replace("+00:00", "Z")
    )
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
        timeout=60,
    )
