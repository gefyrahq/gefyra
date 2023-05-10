from enum import Enum
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

    def test_a_install(self, k3d: AClusterManager, stowaway_image):
        import kubernetes

        kubernetes.config.load_kube_config(config_file=str(k3d.kubeconfig))
        from gefyra.connection.factory import (
            ConnectionProviderType,
            connection_provider_factory,
        )

        os.environ["GEFYRA_STOWAWAY_IMAGE"] = stowaway_image.split(":")[0]
        os.environ["GEFYRA_STOWAWAY_TAG"] = stowaway_image.split(":")[1]
        os.environ["GEFYRA_STOWAWAY_IMAGE_PULLPOLICY"] = "Never"
        self.configuration = OperatorConfiguration()
        k3d.load_image(stowaway_image)

        stowaway = connection_provider_factory.get(
            ConnectionProviderType.STOWAWAY,
            self.configuration,
            logger,
        )
        stowaway.install()
        assert stowaway.installed() is True
        assert stowaway.ready() is False
        k3d.wait(
            "pod/gefyra-stowaway-0",
            "condition=ready",
            namespace="gefyra",
            timeout=120,
        )
        assert stowaway.installed() is True
        assert stowaway.ready() is True

    def test_b_add_peer(self, k3d: AClusterManager):
        import kubernetes

        kubernetes.config.load_kube_config(config_file=str(k3d.kubeconfig))
        from gefyra.connection.factory import (
            ConnectionProviderType,
            connection_provider_factory,
        )

        stowaway = connection_provider_factory.get(
            ConnectionProviderType.STOWAWAY,
            self.configuration,
            logger,
        )
        stowaway.add_peer("test1", {"subnet": "192.168.100.0/24"})

        cm = k3d.kubectl(["get", "configmap", "gefyra-stowaway-config", "-n", "gefyra"])
        assert cm["data"]["PEERS"] == "test1,0"

        output = k3d.kubectl(
            ["exec", "gefyra-stowaway-0", "-n", "gefyra", "--", "ls", "/config"],
            as_dict=False,
        )
        assert "peer_test1" in output
        assert stowaway.peer_exists("test1") is True

    def test_c_add_another_peer(self, k3d: AClusterManager):
        import kubernetes

        kubernetes.config.load_kube_config(config_file=str(k3d.kubeconfig))
        from gefyra.connection.factory import (
            ConnectionProviderType,
            connection_provider_factory,
        )

        stowaway = connection_provider_factory.get(
            ConnectionProviderType.STOWAWAY,
            self.configuration,
            logger,
        )
        stowaway.add_peer("test2", {"subnet": "192.168.101.0/24"})

        cm = k3d.kubectl(["get", "configmap", "gefyra-stowaway-config", "-n", "gefyra"])
        assert cm["data"]["PEERS"] == "test2,test1,0"
        assert cm["data"]["SERVER_ALLOWEDIPS_PEER_test2"] == "192.168.101.0/24"
        k3d.wait(
            "pod/gefyra-stowaway-0",
            "condition=ready",
            namespace="gefyra",
            timeout=120,
        )
        sleep(2)
        output = k3d.kubectl(
            ["exec", "gefyra-stowaway-0", "-n", "gefyra", "--", "ls", "/config"],
            as_dict=False,
        )
        assert "peer_test1" in output
        assert "peer_test2" in output
        assert stowaway.peer_exists("test1") is True
        assert stowaway.peer_exists("test2") is True

    def test_d_get_peer_config(self, k3d: AClusterManager):
        import kubernetes

        kubernetes.config.load_kube_config(config_file=str(k3d.kubeconfig))
        from gefyra.connection.factory import (
            ConnectionProviderType,
            connection_provider_factory,
        )

        stowaway = connection_provider_factory.get(
            ConnectionProviderType.STOWAWAY,
            self.configuration,
            logger,
        )

        peer1_config = stowaway.get_peer_config("test1")
        # {'Interface.Address': '192.168.99.4', 'Interface.PrivateKey': 'MFQ3v+y612uZSsLXjW1smlJIFeDWWFcZCCtmW4mC624=',
        #  'Interface.ListenPort': '51820', 'Interface.DNS': '192.168.99.1',
        #  'Peer.PublicKey': 'sy8jXi7S7rUGpqLnqgKnmHFXylqQdvCPCfhBAgSVGEM=',
        #  'Peer.Endpoint': '79.223.135.126:31820', 'Peer.AllowedIPs': '0.0.0.0/0, ::/0'}
        assert "Interface.PrivateKey" in peer1_config
        assert "Peer.PublicKey" in peer1_config
        assert "Peer.Endpoint" in peer1_config

        peer2_config = stowaway.get_peer_config("test2")
        assert "Interface.PrivateKey" in peer2_config
        assert "Peer.PublicKey" in peer2_config
        assert "Peer.Endpoint" in peer2_config
        assert "Peer.AllowedIPs" in peer2_config

        assert (
            peer1_config["Interface.PrivateKey"] != peer2_config["Interface.PrivateKey"]
        )

    def test_e_remove_peer(self, k3d: AClusterManager):
        import kubernetes

        kubernetes.config.load_kube_config(config_file=str(k3d.kubeconfig))
        from gefyra.connection.factory import (
            ConnectionProviderType,
            connection_provider_factory,
        )

        stowaway = connection_provider_factory.get(
            ConnectionProviderType.STOWAWAY,
            self.configuration,
            logger,
        )
        assert stowaway.remove_peer("test1") is True

        cm = k3d.kubectl(["get", "configmap", "gefyra-stowaway-config", "-n", "gefyra"])
        assert cm["data"]["PEERS"] == "test2,0"
        k3d.wait(
            "pod/gefyra-stowaway-0",
            "condition=ready",
            namespace="gefyra",
            timeout=120,
        )
        sleep(2)
        output = k3d.kubectl(
            ["exec", "gefyra-stowaway-0", "-n", "gefyra", "--", "ls", "/config"],
            as_dict=False,
        )
        assert "peer_test1" not in output
        assert "peer_test2" in output
        assert stowaway.peer_exists("test2") is True
        assert stowaway.peer_exists("test1") is False
        assert stowaway.peer_exists("test3") is False
        k3d.wait(
            "pod/gefyra-stowaway-0",
            "condition=ready",
            namespace="gefyra",
            timeout=120,
        )
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

    def test_f_add_route(self, k3d: AClusterManager):
        from gefyra.connection.factory import (
            ConnectionProviderType,
            connection_provider_factory,
        )

        stowaway = connection_provider_factory.get(
            ConnectionProviderType.STOWAWAY,
            self.configuration,
            logger,
        )
        proxy_host = stowaway.add_destination("test2", "192.168.100.10", 8080)
        assert (
            proxy_host == "gefyra-stowaway-proxy-10000.gefyra.svc.cluster.local:10000"
        )
        proxy_configmap = k3d.kubectl(
            ["-n", "gefyra", "get", "configmap", "gefyra-stowaway-proxyroutes"]
        )
        assert len(proxy_configmap["data"].keys()) == 1
        assert stowaway.destination_exists("test2", "192.168.100.10", 8080) is True
        assert stowaway.destination_exists("test2", "192.168.100.11", 8080) is False

        assert (
            stowaway.get_destination("test2", "192.168.100.10", 8080)
            == "gefyra-stowaway-proxy-10000.gefyra.svc.cluster.local:10000"
        )

        svc = k3d.kubectl(["-n", "gefyra", "get", "svc", "-l", "gefyra.dev/role=proxy"])
        assert len(svc["items"]) == 1

        assert (
            stowaway.add_destination("test2", "192.168.100.11", 8080)
            == "gefyra-stowaway-proxy-10001.gefyra.svc.cluster.local:10001"
        )
        assert (
            stowaway.add_destination("test2", "192.168.100.12", 8080)
            == "gefyra-stowaway-proxy-10002.gefyra.svc.cluster.local:10002"
        )
        assert (
            stowaway.add_destination("test2", "192.168.100.13", 8080)
            == "gefyra-stowaway-proxy-10003.gefyra.svc.cluster.local:10003"
        )
        proxy_configmap = k3d.kubectl(
            ["-n", "gefyra", "get", "configmap", "gefyra-stowaway-proxyroutes"]
        )
        assert len(proxy_configmap["data"].keys()) == 4
        assert len(set(proxy_configmap["data"].values())) == 4

        svc = k3d.kubectl(["-n", "gefyra", "get", "svc", "-l", "gefyra.dev/role=proxy"])
        assert len(svc["items"]) == 4

    def test_g_delete_route(self, k3d: AClusterManager):
        from gefyra.connection.factory import (
            ConnectionProviderType,
            connection_provider_factory,
        )

        stowaway = connection_provider_factory.get(
            ConnectionProviderType.STOWAWAY,
            self.configuration,
            logger,
        )
        stowaway.remove_destination("test2", "192.168.100.10", 8080)

        proxy_configmap = k3d.kubectl(
            ["-n", "gefyra", "get", "configmap", "gefyra-stowaway-proxyroutes"]
        )
        assert len(proxy_configmap["data"].keys()) == 3
        assert "192.168.100.10:8080" not in [
            v.split(",")[0] for v in proxy_configmap["data"].values()
        ]
        svc = k3d.kubectl(["-n", "gefyra", "get", "svc", "-l", "gefyra.dev/role=proxy"])
        assert len(svc["items"]) == 3

    def test_y_provider_notexists(self, k3d: AClusterManager):
        import kubernetes

        kubernetes.config.load_kube_config(config_file=str(k3d.kubeconfig))
        from gefyra.connection.factory import (
            connection_provider_factory,
        )

        class ConnectionProviderType(Enum):
            DOESNOTEXITS = "doesnotexists"

        with pytest.raises(ValueError):
            connection_provider_factory.get(
                ConnectionProviderType.DOESNOTEXITS,
                self.configuration,
                logger,
            )

    def test_z_remove_stowaway(self, k3d: AClusterManager):
        import kubernetes

        kubernetes.config.load_kube_config(config_file=str(k3d.kubeconfig))
        from gefyra.connection.factory import (
            ConnectionProviderType,
            connection_provider_factory,
        )

        stowaway = connection_provider_factory.get(
            ConnectionProviderType.STOWAWAY,
            self.configuration,
            logger,
        )
        stowaway.uninstall()
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
