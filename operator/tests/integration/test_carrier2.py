import logging
from pathlib import Path
from time import sleep
from pytest_kubernetes.providers import AClusterManager


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

        # carrier = Carrier2(
        #     configuration=configuration,
        #     target_namespace=namespace,
        #     target_pod=carrier_pod_name,
        #     target_container="nginx",
        #     logger=logger,
        # )
        # shadow_pod = gefyra_crd.kubectl(
        #     ["get", "pod", shadow_pod_name, "-n", "default"],
        # )
        # container_port = carrier_pod["spec"]["containers"][0]["ports"][0][
        #     "containerPort"
        # ]
        # dest_pod_port = shadow_pod["spec"]["containers"][0]["ports"][0]["containerPort"]
        # dest_host = shadow_pod["status"]["podIP"]

        # carrier.add_proxy_route(
        #     container_port=container_port,
        #     destination_host=dest_host,
        #     destination_port=dest_pod_port,
        # )

        sleep(300)
