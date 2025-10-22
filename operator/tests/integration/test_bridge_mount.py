import logging
from pathlib import Path
from pytest_kubernetes.providers import AClusterManager

logger = logging.getLogger()


class TestBridgeMountObject:
    def test_duplication_by_bridge_mount(self, gefyra_crd: AClusterManager):
        from gefyra.bridge_mount.duplicate import DuplicateBridgeMount

        file_path = str(
            Path(Path(__file__).parent.parent, "fixtures/nginx.yaml").absolute()
        )
        gefyra_crd.apply(file_path)
        name = "nginx-deployment"
        namespace = "default"

        mount = DuplicateBridgeMount(
            configuration=None,
            name=name,
            target_namespace=namespace,
            target=name,
            target_container="nginx",
            logger=logger,
        )
        mount.prepare()

        new_deployment = gefyra_crd.kubectl(
            ["-n", namespace, "get", "deploy", name + "-gefyra"]
        )

        assert new_deployment["metadata"]["name"] == name + "-gefyra"
        assert new_deployment["metadata"]["labels"]["app"] == "nginx-gefyra"
        assert (
            new_deployment["spec"]["selector"]["matchLabels"]["app"] == "nginx-gefyra"
        )
        assert (
            new_deployment["spec"]["template"]["metadata"]["labels"]["app"]
            == "nginx-gefyra"
        )

    def test_removal_of_bridge_mount(self, gefyra_crd: AClusterManager):
        from gefyra.bridge_mount.duplicate import DuplicateBridgeMount

        name = "nginx-deployment"
        namespace = "default"

        mount = DuplicateBridgeMount(
            configuration=None,
            name=name,
            target_namespace=namespace,
            target=name,
            target_container="nginx",
            logger=None,
        )
        mount.uninstall()

        gefyra_crd.wait(
            "deployment/" + name + "-gefyra",
            "delete",
            namespace=namespace,
            timeout=60,
        )
