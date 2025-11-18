import logging
from pathlib import Path
from pytest_kubernetes.providers import AClusterManager

logger = logging.getLogger()


class TestBridgeMountObject:
    def test_a_duplication_by_bridge_mount(self, gefyra_crd: AClusterManager):
        from gefyra.bridge_mount.carrier2mount import Carrier2BridgeMount

        file_path = str(
            Path(Path(__file__).parent.parent, "fixtures/nginx.yaml").absolute()
        )
        gefyra_crd.apply(file_path)
        name = "nginx-deployment"
        namespace = "default"

        mount = Carrier2BridgeMount(
            configuration=None,
            name=name,
            target_namespace=namespace,
            target=f"deploy/{name}",
            target_container="nginx",
            post_event_function=lambda a, b, c: None,
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

    def test_b_removal_of_bridge_mount(self, gefyra_crd: AClusterManager):
        from gefyra.bridge_mount.carrier2mount import Carrier2BridgeMount

        name = "nginx-deployment"
        namespace = "default"

        mount = Carrier2BridgeMount(
            configuration=None,
            name=name,
            target_namespace=namespace,
            target=f"deploy/{name}",
            target_container="nginx",
            post_event_function=lambda a, b, c: None,
            logger=None,
        )
        mount.uninstall()

        gefyra_crd.wait(
            "deployment/" + name + "-gefyra",
            "delete",
            namespace=namespace,
            timeout=60,
        )

    def test_c_duplication_by_bridge_mount_namespace(self, gefyra_crd: AClusterManager):
        from gefyra.bridge_mount.carrier2mount import Carrier2BridgeMount

        namespace = "aaaaaaabbbbbbbbbcccccccdddddddeeeeee-test-432-bb"
        gefyra_crd.kubectl(["create", "ns", namespace])

        file_path = str(
            Path(
                Path(__file__).parent.parent, "fixtures/nginx_namespace.yaml"
            ).absolute()
        )
        gefyra_crd.apply(file_path)
        name = "nginx-deployment"

        mount = Carrier2BridgeMount(
            configuration=None,
            name=name,
            target_namespace=namespace,
            target=f"deploy/{name}",
            target_container="nginx",
            post_event_function=lambda a, b, c: None,
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

    def test_d_removal_of_bridge_mount_namespace(self, gefyra_crd: AClusterManager):
        from gefyra.bridge_mount.carrier2mount import Carrier2BridgeMount

        name = "nginx-deployment"
        namespace = "aaaaaaabbbbbbbbbcccccccdddddddeeeeee-test-432-bb"

        mount = Carrier2BridgeMount(
            configuration=None,
            name=name,
            target_namespace=namespace,
            target=f"deploy/{name}",
            target_container="nginx",
            post_event_function=lambda a, b: None,
            logger=None,
        )
        mount.uninstall()

        gefyra_crd.wait(
            "deployment/" + name + "-gefyra",
            "delete",
            namespace=namespace,
            timeout=60,
        )
        file_path = str(
            Path(
                Path(__file__).parent.parent, "fixtures/nginx_namespace.yaml"
            ).absolute()
        )
        gefyra_crd.kubectl(["delete", "-f", str(file_path)], as_dict=False)
        gefyra_crd.kubectl(["delete", "ns", namespace], as_dict=False)

    def test_a_duplication_by_bridge_mount_sts(self, gefyra_crd: AClusterManager):
        from gefyra.bridge_mount.carrier2mount import Carrier2BridgeMount

        file_path = str(
            Path(Path(__file__).parent.parent, "fixtures/nginx_sts.yaml").absolute()
        )
        gefyra_crd.apply(file_path)
        name = "nginx-sts"
        namespace = "default"

        mount = Carrier2BridgeMount(
            configuration=None,
            name=name,
            target_namespace=namespace,
            target=f"sts/{name}",
            target_container="nginx",
            post_event_function=lambda a, b, c: None,
            logger=logger,
        )
        mount.prepare()

        new_deployment = gefyra_crd.kubectl(
            ["-n", namespace, "get", "sts", name + "-gefyra"]
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
        mount.uninstall()
        gefyra_crd.kubectl(["delete", "-f", str(file_path)], as_dict=False)

    def test_a_duplication_by_bridge_mount_pod(self, gefyra_crd: AClusterManager):
        from gefyra.bridge_mount.carrier2mount import Carrier2BridgeMount
        from gefyra.configuration import OperatorConfiguration

        file_path = str(
            Path(Path(__file__).parent.parent, "fixtures/nginx_pod.yaml").absolute()
        )
        gefyra_crd.apply(file_path)
        name = "nginx-pod"
        namespace = "default"

        mount = Carrier2BridgeMount(
            configuration=OperatorConfiguration(),
            name=name,
            target_namespace=namespace,
            target=f"pod/{name}",
            target_container="nginx",
            post_event_function=lambda a, b, c: None,
            logger=logger,
        )
        mount.prepare()
        try:
            mount.install()
        except:
            pass

        new_deployment = gefyra_crd.kubectl(
            ["-n", namespace, "get", "pod", name + "-gefyra"]
        )

        assert new_deployment["metadata"]["name"] == name + "-gefyra"
        assert new_deployment["metadata"]["labels"]["app"] == "nginx-pod-gefyra"

        mount.uninstall()
        gefyra_crd.kubectl(["delete", "-f", str(file_path)], as_dict=False)
