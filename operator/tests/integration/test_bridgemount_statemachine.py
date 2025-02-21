from unittest.mock import MagicMock

from pathlib import Path
from pytest_kubernetes.providers import AClusterManager


class TestBridgeMountObject:
    def test_duplication_by_bridge_mount_install(self, gefyra_crd: AClusterManager):
        from gefyra.bridgemountstate import GefyraBridgeMount
        from gefyra.bridgemountstate import GefyraBridgeMountObject

        file_path = str(
            Path(Path(__file__).parent.parent, "fixtures/nginx.yaml").absolute()
        )
        gefyra_crd.apply(file_path)
        name = "nginx-deployment"
        namespace = "default"
        bridge_mount_object = GefyraBridgeMountObject(
            data={
                "metadata": {"name": name, "namespace": namespace},
                "state": "REQUESTED",
                "targetNamespace": namespace,
                "target": name,
                "targetContainer": "nginx",
            }
        )
        bridge_mount_object._write_state = MagicMock()

        bridge_mount_machine = GefyraBridgeMount(
            model=bridge_mount_object,
            configuration=None,
            logger=None,
        )
        assert bridge_mount_machine.requested.is_active
        bridge_mount_machine.install()
        assert bridge_mount_machine.installing.is_active

        gefyra_crd.wait(
            "deployment/" + name + "-gefyra",
            "jsonpath='{.status.readyReplicas}'=1",
            namespace=namespace,
            timeout=60,
        )
        bridge_mount_machine.activate()
        assert bridge_mount_machine.active.is_active
