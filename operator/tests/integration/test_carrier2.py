import logging
from pathlib import Path
from time import sleep
from pytest_kubernetes.providers import AClusterManager
import requests
from requests.adapters import HTTPAdapter, Retry


logger = logging.getLogger()


class TestCarrier2:

    def test_carrier2_duplicated_svc_available(self, gefyra_crd: AClusterManager):
        from gefyra.bridge_mount.duplicate import DuplicateBridgeMount
        from gefyra.configuration import OperatorConfiguration

        nginx_fixture = str(
            Path(Path(__file__).parent.parent, "fixtures/nginx.yaml").absolute()
        )
        bridge_mount_fixture = str(
            Path(Path(__file__).parent.parent, "fixtures/bridge_mount.yaml").absolute()
        )  # needed as for bridge mount and bridge (target is shared through this object)
        gefyra_crd.apply(nginx_fixture)
        gefyra_crd.apply(bridge_mount_fixture)
        name = "nginx-deployment"
        configuration = OperatorConfiguration()
        namespace = "default"

        mount = DuplicateBridgeMount(
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
