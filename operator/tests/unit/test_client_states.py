import json
import logging
from time import sleep
import pytest

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
        client.create()
        client_a = k3d.kubectl(["-n", "gefyra", "get", "gefyraclient", "client-a"])
        assert client_a["state"] == "CREATING"
        assert client_a.get("stateTransitions") is not None

    def test_d_client_exit_creating(self, gefyra_crd: AClusterManager):
        from gefyra.clientstate import GefyraClient, GefyraClientObject
        from gefyra.configuration import OperatorConfiguration
        import kopf

        k3d = gefyra_crd
        client_a = k3d.kubectl(["-n", "gefyra", "get", "gefyraclient", "client-a"])
        obj = GefyraClientObject(client_a)
        client = GefyraClient(obj, OperatorConfiguration(), logger)
        assert client.creating.is_active is True

        exception_raised = False
        _i = 0
        while _i < 10:
            try:
                client.create()
            except kopf.TemporaryError:
                sleep(1)
                _i += 1
                continue
            else:
                break
        client_a = k3d.kubectl(["-n", "gefyra", "get", "gefyraclient", "client-a"])
        assert client_a["state"] == "WAITING"
        assert client_a.get("stateTransitions") is not None

    # @pytest.mark.asyncio
    # async def test_f_client_activating(self, gefyra_crd: AClusterManager):
    #     from gefyra.clientstate import GefyraClient, GefyraClientObject
    #     from gefyra.configuration import OperatorConfiguration
    #     from gefyra.connection.stowaway.components import handle_config_configmap

    #     k3d = gefyra_crd
    #     patch = json.dumps({"providerParameter": {"subnet": "192.168.101.0/24"}})
    #     client_a = k3d.kubectl(
    #         [
    #             "-n",
    #             "gefyra",
    #             "patch",
    #             "gefyraclient",
    #             "client-a",
    #             "--type='merge'",
    #             f"--patch='{patch}'",
    #         ]
    #     )
    #     obj = GefyraClientObject(client_a)
    #     client = GefyraClient(obj, OperatorConfiguration(), logger)
    #     # for stowaway
    #     await client.enable()
    #     client_a = k3d.kubectl(["-n", "gefyra", "get", "gefyraclient", "client-a"])
    #     assert client_a["state"] == "ENABLING"
    #     assert client_a.get("stateTransitions") is not None
    #     assert client_a["providerConfig"] is not None

    # def test_g_client_deactivating(self, gefyra_crd: AClusterManager):
    #     from gefyra.clientstate import GefyraClient, GefyraClientObject
    #     from gefyra.configuration import OperatorConfiguration

    #     k3d = gefyra_crd
    #     obj = GefyraClientObject(client_a)
    #     client = GefyraClient(obj, OperatorConfiguration(), logger)
    #     client.disabling()
    #     client_a = k3d.kubectl(["-n", "gefyra", "get", "gefyraclient", "client-a"])
    #     assert client_a["state"] == "WAITING"
    #     assert client_a.get("stateTransitions") is not None
    #     assert client_a["providerConfig"] is None
    #     assert client_a["providerParameters"] is None

    # def test_h_client_reactivating(self, gefyra_crd: AClusterManager):
    #     from gefyra.clientstate import GefyraClient, GefyraClientObject
    #     from gefyra.configuration import OperatorConfiguration

    #     k3d = gefyra_crd
    #     patch = json.dumps({"providerParameter": {"subnet": "192.168.101.0/24"}})
    #     client_a = k3d.kubectl(
    #         [
    #             "-n",
    #             "gefyra",
    #             "patch",
    #             "gefyraclient",
    #             "client-a",
    #             "--type='merge'",
    #             f"--patch='{patch}'",
    #         ]
    #     )
    #     obj = GefyraClientObject(client_a)
    #     client = GefyraClient(obj, OperatorConfiguration(), logger)
    #     client.enable()
    #     client_a = k3d.kubectl(["-n", "gefyra", "get", "gefyraclient", "client-a"])
    #     assert client_a["state"] == "ACTIVE"
    #     assert client_a.get("stateTransitions") is not None
    #     assert client_a["providerConfig"] is not None
