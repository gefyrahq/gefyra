import logging
from pathlib import Path
from time import sleep
import time
from pytest_kubernetes.providers import AClusterManager
import requests
from requests.adapters import HTTPAdapter, Retry

from tests.integration.utils import read_carrier2_config


logger = logging.getLogger()


class TestCarrier2:

    def test_a_commit_config(self, gefyra_crd: AClusterManager, carrier2_image):

        from gefyra.bridge.carrier2.config import Carrier2Config

        test_pod = str(
            Path(Path(__file__).parent.parent, "fixtures/test_pod.yaml").absolute()
        )
        gefyra_crd.load_image(carrier2_image)
        gefyra_crd.apply(test_pod)

        gefyra_crd.wait(
            "pod/backend",
            "condition=ready",
            namespace="default",
            timeout=60,
        )

        config = Carrier2Config()
        config.clusterUpstream = ["blueshoe.io:443"]
        config.port = 5000
        start = time.time()
        config.commit(
            pod_name="backend",
            container_name="backend",
            namespace="default",
            debug=True,
        )
        end = time.time()
        # print(f"commit time: {end - start}")

        from kubernetes.client.api import core_v1_api

        core_v1 = core_v1_api.CoreV1Api()
        config = read_carrier2_config(core_v1, "backend", "default")
        config = config[0].replace("\n", "").replace(" ", "")
        assert (
            "version:1threads:4port:5000error_log:/tmp/carrier.logpid_file:/tmp/carrier2.pidupgrade_sock:/tmp/carrier2.sockupstream_keepalive_pool_size:100clusterUpstream:-blueshoe.io:443"
            in config
        )

    def test_carrier2_duplicated_svc_available(self, gefyra_crd: AClusterManager):
        from gefyra.bridge_mount.carrier2mount import Carrier2BridgeMount
        from gefyra.configuration import OperatorConfiguration

        nginx_fixture = str(
            Path(Path(__file__).parent.parent, "fixtures/nginx.yaml").absolute()
        )
        bridge_mount_fixture = str(
            Path(Path(__file__).parent.parent, "fixtures/bridge_mount.yaml").absolute()
        )  # needed as for bridge mount and bridge (target is shared through this object)
        gefyra_crd.apply(nginx_fixture)
        gefyra_crd.wait(
            "deployment/nginx-deployment",
            "jsonpath='{.status.readyReplicas}'=1",
            namespace="default",
            timeout=60,
        )
        gefyra_crd.apply(bridge_mount_fixture)
        name = "nginx-deployment"
        configuration = OperatorConfiguration()
        namespace = "default"

        mount = Carrier2BridgeMount(
            name="bridgemount-a",
            configuration=configuration,
            target_namespace=namespace,
            target=name,
            target_container="nginx",
            logger=logger,
        )
        mount.prepare()
        # todo reconcile eventually
        mount.install()
        retries = Retry(total=60, backoff_factor=0.2, status_forcelist=[404, 500])
        session = requests.Session()
        session.mount("http://localhost:8080", HTTPAdapter(max_retries=retries))

        # the is now served from backend-shadow (from the cluster) via Carrier2
        content_retries = 10
        while content_retries > 0:
            try:
                resp = session.get("http://localhost:8080")
                assert resp.status_code == 200
                assert "Welcome to nginx!" in resp.text
                return
            except AssertionError:
                print("Retrying to get the expected response from the service")
                content_retries -= 1
                sleep(1)
        raise AssertionError(
            f"Could not get the expected response from the service. Got: {resp.text}"
        )
