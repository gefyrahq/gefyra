import json
import logging
from time import sleep
import kopf

from pytest_kubernetes.providers import AClusterManager


logger = logging.getLogger()


class TestClientStates:
    def test_a_apply_client(self, gefyra_crd: AClusterManager):
        k3d = gefyra_crd
        k3d.apply("tests/fixtures/a_gefyra_client.yaml")
        client_a = k3d.kubectl(["-n", "gefyra", "get", "gefyraclient", "client-a"])
        assert client_a["state"] == "REQUESTED"
        assert client_a.get("stateTransitions") is None

    def test_b_load_client(self, gefyra_crd: AClusterManager):
        from gefyra.clientstate import GefyraClient, GefyraClientObject
        from gefyra.configuration import OperatorConfiguration

        k3d = gefyra_crd
        client_a = k3d.kubectl(["-n", "gefyra", "get", "gefyraclient", "client-a"])
        obj = GefyraClientObject(client_a)
        GefyraClient(obj, OperatorConfiguration(), logger)

    def test_c_client_enter_creating(self, gefyra_crd: AClusterManager):
        from gefyra.clientstate import GefyraClient, GefyraClientObject
        from gefyra.configuration import OperatorConfiguration

        k3d = gefyra_crd
        client_a = k3d.kubectl(["-n", "gefyra", "get", "gefyraclient", "client-a"])
        obj = GefyraClientObject(client_a)
        client = GefyraClient(obj, OperatorConfiguration(), logger)
        assert client.requested.is_active is True
        _i = 0
        while _i < 10:
            try:
                client.create()
            except:
                client_a = k3d.kubectl(
                    ["-n", "gefyra", "get", "gefyraclient", "client-a"]
                )
                assert (
                    client_a["state"] == "REQUESTED" or client_a["state"] == "CREATING"
                )
                sleep(1)
                _i += 1
                continue
            else:
                break

        client_a = k3d.kubectl(["-n", "gefyra", "get", "gefyraclient", "client-a"])
        assert client_a["state"] == "WAITING"
        assert client_a.get("stateTransitions") is not None
        client.get_latest_state()
