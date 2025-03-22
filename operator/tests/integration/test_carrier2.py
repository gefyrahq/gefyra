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

        file_path = str(
            Path(Path(__file__).parent.parent, "fixtures/nginx.yaml").absolute()
        )
        gefyra_crd.apply(file_path)
        name = "nginx-deployment"
        configuration = OperatorConfiguration()
        namespace = "default"

        mount = DuplicateBridgeMount(
            configuration=configuration,
            target_namespace=namespace,
            target=name,
            target_container="nginx",
            logger=logger,
        )
        mount.prepare()

        sleep(10)
        mount.install()

        retries = Retry(total=10, backoff_factor=0.2)
        session = requests.Session()
        session.mount("http://localhost:8080", HTTPAdapter(max_retries=retries))

        # the is now served from backend-shadow (from the cluster) via Carrier2
        resp = session.get("http://localhost:8080")
        assert resp.status_code == 200
        assert "Welcome to nginx!" in resp.text
