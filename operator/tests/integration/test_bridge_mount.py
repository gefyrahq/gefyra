import logging
from pathlib import Path
from pytest_kubernetes.providers import AClusterManager

from tests.utils import post_event_noop

logger = logging.getLogger()


class TestBridgeMountObject:
    async def test_a_duplication_by_bridge_mount(self, gefyra_crd: AClusterManager):
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
            post_event_function=post_event_noop,
            logger=logger,
        )
        await mount.prepare()

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

    async def test_b_removal_of_bridge_mount(self, gefyra_crd: AClusterManager):
        from gefyra.bridge_mount.carrier2mount import Carrier2BridgeMount

        name = "nginx-deployment"
        namespace = "default"

        mount = Carrier2BridgeMount(
            configuration=None,
            name=name,
            target_namespace=namespace,
            target=f"deploy/{name}",
            target_container="nginx",
            post_event_function=post_event_noop,
            logger=None,
        )
        await mount.uninstall()

        gefyra_crd.wait(
            "deployment/" + name + "-gefyra",
            "delete",
            namespace=namespace,
            timeout=60,
        )

    async def test_c_duplication_by_bridge_mount_namespace(
        self, gefyra_crd: AClusterManager
    ):
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
            post_event_function=post_event_noop,
            logger=logger,
        )
        await mount.prepare()

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

    async def test_d_removal_of_bridge_mount_namespace(
        self, gefyra_crd: AClusterManager
    ):
        from gefyra.bridge_mount.carrier2mount import Carrier2BridgeMount

        name = "nginx-deployment"
        namespace = "aaaaaaabbbbbbbbbcccccccdddddddeeeeee-test-432-bb"

        mount = Carrier2BridgeMount(
            configuration=None,
            name=name,
            target_namespace=namespace,
            target=f"deploy/{name}",
            target_container="nginx",
            post_event_function=post_event_noop,
            logger=None,
        )
        await mount.uninstall()

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

    async def test_a_duplication_by_bridge_mount_sts(self, gefyra_crd: AClusterManager):
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
            post_event_function=post_event_noop,
            logger=logger,
        )
        await mount.prepare()

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
        await mount.uninstall()
        gefyra_crd.kubectl(["delete", "-f", str(file_path)], as_dict=False)

    async def test_a_duplication_by_bridge_mount_pod(self, gefyra_crd: AClusterManager):
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
            post_event_function=post_event_noop,
            logger=logger,
        )
        await mount.prepare()
        try:
            await mount.install()
        except Exception:
            pass

        new_deployment = gefyra_crd.kubectl(
            ["-n", namespace, "get", "pod", name + "-gefyra"]
        )

        assert new_deployment["metadata"]["name"] == name + "-gefyra"
        assert new_deployment["metadata"]["labels"]["app"] == "nginx-pod-gefyra"

        await mount.uninstall()
        gefyra_crd.kubectl(["delete", "-f", str(file_path)], as_dict=False)
