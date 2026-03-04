from time import sleep
from gefyra.types import GefyraClient, GefyraClientState
import pytest
from pytest_kubernetes.providers import AClusterManager
from tests.e2e.base import GefyraTestCase


class TestGefyraClients(GefyraTestCase):
    def test_a_create_client(self, operator: AClusterManager):
        k3d = operator
        from gefyra.api.clients import add_clients

        gclient = add_clients("client-a", kubeconfig=operator.kubeconfig)[0]
        client_a: GefyraClient = k3d.kubectl(
            ["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"]
        )
        assert client_a["state"] is not None
        gclient.get_client_config(gefyra_server="localhost:31820")
        k3d.wait(
            "gefyraclients.gefyra.dev/client-a",
            "jsonpath=.state=WAITING",
            namespace="gefyra",
            timeout=60,
        )
        assert gclient.state is GefyraClientState.WAITING

    def test_b_get_client(self, operator: AClusterManager):
        k3d = operator
        from gefyra.api.clients import get_client

        gclient = get_client("client-a", kubeconfig=operator.kubeconfig)
        gclient.wait_for_state(GefyraClientState.WAITING)

        assert gclient.provider_parameter is None
        assert gclient.provider_config is None
        k3d.kubectl(["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-a"])
        config = gclient.get_client_config(gefyra_server="localhost:31820")
        assert config.kubernetes_server is not None

        no_sa = self.run_operator_with_sa(operator)
        # if this is disabled SA
        print(
            k3d.kubectl(
                ["logs", "-n", "gefyra", "deployment/gefyra-operator"], as_dict=False
            )
        )

        if no_sa:
            assert config.ca_crt is None
            assert config.namespace is not None
            assert config.token is None
        else:
            assert config.ca_crt is not None
            assert config.namespace is not None
            assert config.token is not None

    def test_c_create_clients(self, operator: AClusterManager):
        k3d = operator
        k3d.version()
        from gefyra.api.clients import add_clients

        for client in ["client-b", "client-c", "client-d", "client-e", "client-f"]:
            add_clients(client, kubeconfig=operator.kubeconfig)

    def test_d_delete_client(self, operator: AClusterManager):
        k3d = operator
        from gefyra.api.clients import delete_client

        delete_client("client-f", kubeconfig=operator.kubeconfig)
        sleep(5)
        with pytest.raises(RuntimeError):
            k3d.kubectl(["-n", "gefyra", "get", "gefyraclients.gefyra.dev", "client-f"])

    def test_e_failing_reconnect(self, operator: AClusterManager, tmp_path):
        import docker

        self.cmd(
            operator.kubeconfig, "client", ["create", "--client-id", "client-recon"]
        )

        operator.wait(
            "gefyraclients.gefyra.dev/client-recon",
            "jsonpath=.state=WAITING",
            namespace="gefyra",
            timeout=60,
        )
        client_file_path = tmp_path / "client-recon.json"
        self.cmd(
            operator.kubeconfig,
            "client",
            ["config", "-o", client_file_path, "client-recon", "--local"],
        )

        self.cmd(
            operator.kubeconfig,
            "connection",
            ["connect", "-f", client_file_path, "--connection-name", "recon-test"],
        )

        operator.wait(
            "gefyraclients.gefyra.dev/client-recon",
            "jsonpath=.state=ACTIVE",
            namespace="gefyra",
            timeout=60,
        )

        docker_client = docker.from_env()
        docker_client.containers.get("gefyra-cargo-recon-test").remove(force=True)
        with pytest.raises(AssertionError) as excinfo:
            self.cmd(
                operator.kubeconfig,
                "connection",
                ["connect", "-f", client_file_path, "--connection-name", "recon-test"],
            )
        assert "is already active" in str(excinfo.value)

        self.cmd(
            operator.kubeconfig,
            "connection",
            [
                "connect",
                "-f",
                client_file_path,
                "--connection-name",
                "recon-test",
                "--force",
            ],
        )

        operator.wait(
            "gefyraclients.gefyra.dev/client-recon",
            "jsonpath=.state=ACTIVE",
            namespace="gefyra",
            timeout=60,
        )

        self.cmd(
            operator.kubeconfig,
            "connection",
            ["rm", "recon-test"],
        )
