import logging
import os
from time import sleep
import pytest
import kubernetes
from pytest_kubernetes.providers import AClusterManager


from gefyra.configuration import OperatorConfiguration
from gefyra.connection.stowaway.components import handle_serviceaccount

logger = logging.getLogger(__name__)


class TestStowaway:
    configuration = OperatorConfiguration()

    @pytest.mark.asyncio
    async def test_a_install(self, k3d: AClusterManager, stowaway_image):
        kubernetes.config.load_kube_config(config_file=str(k3d.kubeconfig))
        from gefyra.connection.factory import ProviderType, connection_provider_factory

        os.environ["GEFYRA_STOWAWAY_IMAGE"] = stowaway_image.split(":")[0]
        os.environ["GEFYRA_STOWAWAY_TAG"] = stowaway_image.split(":")[1]
        os.environ["GEFYRA_STOWAWAY_IMAGE_PULLPOLICY"] = "Never"
        self.configuration = OperatorConfiguration()
        k3d.load_image(stowaway_image)

        stowaway = connection_provider_factory.get(
            ProviderType.STOWAWAY,
            self.configuration,
            logger,
        )
        await stowaway.install()
        assert await stowaway.installed() is True
        assert await stowaway.ready() is False
        sleep(5)
        k3d.wait(
            "pod/gefyra-stowaway-0",
            "condition=ready",
            namespace="gefyra",
            timeout=120,
        )
        assert await stowaway.installed() is True
        assert await stowaway.ready() is True

    @pytest.mark.asyncio
    async def test_b_add_peer(self, k3d: AClusterManager):
        kubernetes.config.load_kube_config(config_file=str(k3d.kubeconfig))
        from gefyra.connection.factory import ProviderType, connection_provider_factory

        stowaway = connection_provider_factory.get(
            ProviderType.STOWAWAY,
            self.configuration,
            logger,
        )
        assert await stowaway.add_peer("test1") is True

        cm = k3d.kubectl(["get", "configmap", "gefyra-stowaway-config", "-n", "gefyra"])
        assert cm["data"]["PEERS"] == "test1,0"

        output = k3d.kubectl(
            ["exec", "gefyra-stowaway-0", "-n", "gefyra", "--", "ls", "/config"],
            as_dict=False,
        )
        assert "peer_test1" in output
        assert await stowaway.peer_exists("test1") is True

    @pytest.mark.asyncio
    async def test_c_add_another_peer(self, k3d: AClusterManager):
        kubernetes.config.load_kube_config(config_file=str(k3d.kubeconfig))
        from gefyra.connection.factory import ProviderType, connection_provider_factory

        stowaway = connection_provider_factory.get(
            ProviderType.STOWAWAY,
            self.configuration,
            logger,
        )
        assert await stowaway.add_peer("test2") is True

        cm = k3d.kubectl(["get", "configmap", "gefyra-stowaway-config", "-n", "gefyra"])
        assert cm["data"]["PEERS"] == "test2,test1,0"

        output = k3d.kubectl(
            ["exec", "gefyra-stowaway-0", "-n", "gefyra", "--", "ls", "/config"],
            as_dict=False,
        )
        assert "peer_test1" in output
        assert "peer_test2" in output
        assert await stowaway.peer_exists("test1") is True
        assert await stowaway.peer_exists("test2") is True

    @pytest.mark.asyncio
    async def test_d_remove_peer(self, k3d: AClusterManager):
        kubernetes.config.load_kube_config(config_file=str(k3d.kubeconfig))
        from gefyra.connection.factory import ProviderType, connection_provider_factory

        stowaway = connection_provider_factory.get(
            ProviderType.STOWAWAY,
            self.configuration,
            logger,
        )
        assert await stowaway.remove_peer("test1") is True

        cm = k3d.kubectl(["get", "configmap", "gefyra-stowaway-config", "-n", "gefyra"])
        assert cm["data"]["PEERS"] == "test2,0"

        output = k3d.kubectl(
            ["exec", "gefyra-stowaway-0", "-n", "gefyra", "--", "ls", "/config"],
            as_dict=False,
        )
        assert "peer_test1" not in output
        assert "peer_test2" in output
        assert await stowaway.peer_exists("test2") is True
        assert await stowaway.peer_exists("test1") is False
        assert await stowaway.peer_exists("test3") is False

    @pytest.mark.asyncio
    async def test_e_remove_stowaway(self, k3d: AClusterManager):
        kubernetes.config.load_kube_config(config_file=str(k3d.kubeconfig))
        from gefyra.connection.factory import ProviderType, connection_provider_factory

        stowaway = connection_provider_factory.get(
            ProviderType.STOWAWAY,
            self.configuration,
            logger,
        )
        await stowaway.uninstall()
        output = k3d.kubectl(
            ["get", "sts", "-n", "gefyra"],
            as_dict=False,
        )
        assert "gefyra-stowaway" not in output
        output = k3d.kubectl(
            ["get", "svc", "-n", "gefyra"],
            as_dict=False,
        )
        assert "stowaway" not in output
