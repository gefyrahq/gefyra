import json

from pytest_kubernetes.providers import AClusterManager

from gefyra.api.clients import write_client_file
from gefyra.types import GefyraClient

from tests.e2e.base import GefyraTestCase


class TestCustomRegistry(GefyraTestCase):

    def test_a_write_client_file(self, operator: AClusterManager):
        k3d = operator
        from gefyra.api.clients import add_clients

        add_clients("client-a", kubeconfig=operator.kubeconfig)
        client_a: GefyraClient = k3d.kubectl(
            ["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"]
        )

        assert client_a["state"] is not None

        k3d.wait(
            "gefyraclients.gefyra.dev/client-a",
            "jsonpath=.state=WAITING",
            namespace="gefyra",
            timeout=20,
        )

        # connect client
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

        client_file_str = write_client_file(
            client_id="client-a",
            host="localhost",
            port="31820",
            kubeconfig=k3d.kubeconfig,
            kubecontext=k3d.context,
        )

        client_file_json = json.loads(client_file_str)

        assert client_file_json["wireguard_mtu"] == "1340"

    def test_b_write_client_file_without_registry_and_mtu(
        self, operator: AClusterManager
    ):
        k3d = operator

        client_a: GefyraClient = k3d.kubectl(
            ["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"]
        )

        assert client_a["state"] is not None

        k3d.wait(
            "gefyraclients.gefyra.dev/client-a",
            "jsonpath=.state=ACTIVE",
            namespace="gefyra",
            timeout=20,
        )

        client_file_str = write_client_file(
            client_id="client-a",
            host="localhost",
            port="31820",
            kubeconfig=k3d.kubeconfig,
            kubecontext=k3d.context,
        )

        client_file_json = json.loads(client_file_str)

        assert client_file_json["wireguard_mtu"] == "1340"
        assert client_file_json["registry"] is None

    def test_c_write_client_file_with_registry_and_mtu(self, operator: AClusterManager):
        k3d = operator

        client_a: GefyraClient = k3d.kubectl(
            ["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"]
        )

        assert client_a["state"] is not None

        k3d.wait(
            "gefyraclients.gefyra.dev/client-a",
            "jsonpath=.state=ACTIVE",
            namespace="gefyra",
            timeout=20,
        )

        client_file_str = write_client_file(
            client_id="client-a",
            host="localhost",
            port="31820",
            kubeconfig=k3d.kubeconfig,
            kubecontext=k3d.context,
            registry="kuchen.io/gefyra",
            wireguard_mtu=570,
        )

        client_file_json = json.loads(client_file_str)

        assert client_file_json["wireguard_mtu"] == "570"
        assert client_file_json["registry"] == "kuchen.io/gefyra"
