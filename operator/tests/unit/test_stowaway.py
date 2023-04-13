import logging
import os
from time import sleep
import pytest

from pytest_kubernetes.providers import AClusterManager


from gefyra.configuration import OperatorConfiguration

logger = logging.getLogger(__name__)

# TODO: Add tests for:
# - correct labels set on all resources
# - service account


class TestStowaway:
    configuration = OperatorConfiguration()

    @pytest.mark.asyncio
    async def test_a_install(self, k3d: AClusterManager, stowaway_image):
        import kubernetes
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
        import kubernetes
        kubernetes.config.load_kube_config(config_file=str(k3d.kubeconfig))
        from gefyra.connection.factory import ProviderType, connection_provider_factory

        stowaway = connection_provider_factory.get(
            ProviderType.STOWAWAY,
            self.configuration,
            logger,
        )
        assert await stowaway.add_peer("test1", {"subnet": "192.168.100.0/24"}) is True

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
        import kubernetes
        kubernetes.config.load_kube_config(config_file=str(k3d.kubeconfig))
        from gefyra.connection.factory import ProviderType, connection_provider_factory

        stowaway = connection_provider_factory.get(
            ProviderType.STOWAWAY,
            self.configuration,
            logger,
        )
        assert await stowaway.add_peer("test2", {"subnet": "192.168.101.0/24"}) is True

        cm = k3d.kubectl(["get", "configmap", "gefyra-stowaway-config", "-n", "gefyra"])
        assert cm["data"]["PEERS"] == "test2,test1,0"
        assert cm["data"]["SERVER_ALLOWEDIPS_PEER_test2"] == "192.168.101.0/24"
        sleep(1)
        output = k3d.kubectl(
            ["exec", "gefyra-stowaway-0", "-n", "gefyra", "--", "ls", "/config"],
            as_dict=False,
        )
        assert "peer_test1" in output
        assert "peer_test2" in output
        assert await stowaway.peer_exists("test1") is True
        assert await stowaway.peer_exists("test2") is True

    @pytest.mark.asyncio
    async def test_d_get_peer_config(self, k3d: AClusterManager):
        import kubernetes
        kubernetes.config.load_kube_config(config_file=str(k3d.kubeconfig))
        from gefyra.connection.factory import ProviderType, connection_provider_factory

        stowaway = connection_provider_factory.get(
            ProviderType.STOWAWAY,
            self.configuration,
            logger,
        )

        peer1_config = await stowaway.get_peer_config("test1")
        # {'Interface.Address': '192.168.99.4', 'Interface.PrivateKey': 'MFQ3v+y612uZSsLXjW1smlJIFeDWWFcZCCtmW4mC624=',
        #  'Interface.ListenPort': '51820', 'Interface.DNS': '192.168.99.1',
        #  'Peer.PublicKey': 'sy8jXi7S7rUGpqLnqgKnmHFXylqQdvCPCfhBAgSVGEM=',
        #  'Peer.Endpoint': '79.223.135.126:31820', 'Peer.AllowedIPs': '0.0.0.0/0, ::/0'}
        assert "Interface.PrivateKey" in peer1_config
        assert "Peer.PublicKey" in peer1_config
        assert "Peer.Endpoint" in peer1_config

        peer2_config = await stowaway.get_peer_config("test2")
        assert "Interface.PrivateKey" in peer2_config
        assert "Peer.PublicKey" in peer2_config
        assert "Peer.Endpoint" in peer2_config
        assert "Peer.AllowedIPs" in peer2_config

        assert (
            peer1_config["Interface.PrivateKey"] != peer2_config["Interface.PrivateKey"]
        )

    @pytest.mark.asyncio
    async def test_e_remove_peer(self, k3d: AClusterManager):
        import kubernetes
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
        sleep(1)
        output = k3d.kubectl(
            ["exec", "gefyra-stowaway-0", "-n", "gefyra", "--", "ls", "/config"],
            as_dict=False,
        )
        assert "peer_test1" not in output
        assert "peer_test2" in output
        assert await stowaway.peer_exists("test2") is True
        assert await stowaway.peer_exists("test1") is False
        assert await stowaway.peer_exists("test3") is False
        output = k3d.kubectl(
            [
                "exec",
                "gefyra-stowaway-0",
                "-n",
                "gefyra",
                "--",
                "cat",
                "/config/wg0.conf",
            ],
            as_dict=False,
        )
        assert "192.168.100.0/24" not in output
        assert "192.168.101.0/24" in output

    @pytest.mark.asyncio
    async def test_z_remove_stowaway(self, k3d: AClusterManager):
        import kubernetes
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
