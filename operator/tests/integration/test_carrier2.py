import logging
from pathlib import Path
from time import sleep
from pytest_kubernetes.providers import AClusterManager


logger = logging.getLogger()


class TestCarrier2:
    def test_carrier2_duplicated_svc_available(self, gefyra_crd: AClusterManager):
        from gefyra.bridge_mount.duplicate import DuplicateBridgeMount
        from gefyra.bridge.carrier2 import Carrier2
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

        res = gefyra_crd.kubectl(
            ["get", "pod", "-n", "default"],
        )
        carrier_pod = next(
            filter(
                lambda x: "nginx-deployment" in x["metadata"]["name"]
                and "gefyra" not in x["metadata"]["name"],
                res["items"],
            )
        )
        shadow_pod = next(
            filter(
                lambda x: "nginx-deployment-gefyra" in x["metadata"]["name"],
                res["items"],
            )
        )
        print(carrier_pod)
        print("==============================")
        print(shadow_pod)
        carrier_pod_name = carrier_pod["metadata"]["name"]
        shadow_pod_name = shadow_pod["metadata"]["name"]
        carrier_pod = gefyra_crd.kubectl(
            ["get", "pod", carrier_pod_name, "-n", "default"],
        )

        assert carrier_pod is not None

        sleep(10)
        mount.install()

        carrier = Carrier2(
            configuration=configuration,
            target_namespace=namespace,
            target_pod=carrier_pod_name,
            target_container="nginx",
            logger=logger,
        )
        sleep(30)
        shadow_pod = gefyra_crd.kubectl(
            ["get", "pod", shadow_pod_name, "-n", "default"],
        )
        container_port = carrier_pod["spec"]["containers"][0]["ports"][0][
            "containerPort"
        ]
        dest_pod_port = shadow_pod["spec"]["containers"][0]["ports"][0]["containerPort"]
        dest_host = shadow_pod["status"]["podIP"]

        carrier.add_proxy_route(
            container_port=container_port,
            destination_host=dest_host,
            destination_port=dest_pod_port,
        )
