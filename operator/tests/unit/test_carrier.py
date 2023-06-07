import logging
import os
import pytest
from pytest_kubernetes.providers import AClusterManager

from gefyra.configuration import OperatorConfiguration

logger = logging.getLogger(__name__)


@pytest.fixture
def operator_config(carrier_image):
    os.environ["GEFYRA_CARRIER_IMAGE"] = carrier_image.split(":")[0]
    os.environ["GEFYRA_CARRIER_IMAGE_TAG"] = carrier_image.split(":")[1]
    return OperatorConfiguration()


class TestCarrier:
    def test_a_install(
        self,
        k3d: AClusterManager,
        demo_backend_image,
        demo_frontend_image,
        carrier_image,
        operator_config,
    ):
        import kubernetes

        k3d.load_image(demo_backend_image)
        k3d.load_image(demo_frontend_image)
        k3d.load_image(carrier_image)

        kubernetes.config.load_kube_config(config_file=str(k3d.kubeconfig))
        from gefyra.bridge.factory import (
            BridgeProviderType,
            bridge_provider_factory,
        )

        k3d.kubectl(["create", "namespace", "demo"])
        k3d.wait("ns/demo", "jsonpath='{.status.phase}'=Active")
        k3d.apply("tests/fixtures/demo_pods.yaml")
        k3d.wait(
            "pod/backend",
            "condition=ready",
            namespace="demo",
            timeout=60,
        )

        carrier = bridge_provider_factory.get(
            BridgeProviderType.CARRIER,
            operator_config,
            "demo",
            "backend",
            "backend",
            logger,
        )
        assert carrier.installed() is False
        carrier.install()
        backend_pod = k3d.kubectl(["get", "pod", "backend", "-n", "demo"])
        assert backend_pod["spec"]["containers"][0]["image"] == carrier_image

    def test_b_installed(self, k3d: AClusterManager, operator_config):
        from gefyra.bridge.factory import (
            BridgeProviderType,
            bridge_provider_factory,
        )

        carrier = bridge_provider_factory.get(
            BridgeProviderType.CARRIER,
            operator_config,
            "demo",
            "backend",
            "backend",
            logger,
        )
        # at this point, the carrier should be installed, but not ready
        assert carrier.installed() is True

    def test_c_ready(self, k3d: AClusterManager, operator_config, carrier_image):
        from gefyra.bridge.factory import (
            BridgeProviderType,
            bridge_provider_factory,
        )

        carrier = bridge_provider_factory.get(
            BridgeProviderType.CARRIER,
            operator_config,
            "demo",
            "backend",
            "backend",
            logger,
        )
        k3d.wait(
            "pod/backend",
            "jsonpath=.status.containerStatuses[0].image=docker.io/library/"
            + carrier_image,
            namespace="demo",
            timeout=60,
        )
        assert carrier.ready() is True

    def test_d_addproxyroute(self, k3d: AClusterManager, operator_config):
        from gefyra.bridge.factory import (
            BridgeProviderType,
            bridge_provider_factory,
        )

        carrier = bridge_provider_factory.get(
            BridgeProviderType.CARRIER,
            operator_config,
            "demo",
            "backend",
            "backend",
            logger,
        )
        carrier.add_proxy_route(80, "host", 8080)
        output = k3d.kubectl(
            ["-n", "demo", "exec", "backend", "--", "cat", "/etc/nginx/nginx.conf"],
            as_dict=False,
        )
        assert "upstream stowaway-80 {server host:8080;}" in output
        assert carrier.proxy_route_exists(80, "host", 8080) is True
        assert carrier.proxy_route_exists(8080, "host-1", 8081) is False

    def test_e_removeproxyroute(self, k3d: AClusterManager, operator_config):
        from gefyra.bridge.factory import (
            BridgeProviderType,
            bridge_provider_factory,
        )

        carrier = bridge_provider_factory.get(
            BridgeProviderType.CARRIER,
            operator_config,
            "demo",
            "backend",
            "backend",
            logger,
        )
        carrier.remove_proxy_route(80, "host", 8080)

    def test_z_uninstall(self, k3d: AClusterManager, operator_config, carrier_image):
        from gefyra.bridge.factory import (
            BridgeProviderType,
            bridge_provider_factory,
        )

        carrier = bridge_provider_factory.get(
            BridgeProviderType.CARRIER,
            operator_config,
            "demo",
            "backend",
            "backend",
            logger,
        )
        carrier.uninstall()
        k3d.wait(
            "pod/backend",
            "jsonpath=.status.containerStatuses[0].image=quay.io/gefyra/gefyra-demo-backend:latest",
            namespace="demo",
            timeout=60,
        )
