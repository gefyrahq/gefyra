import logging
from unittest.mock import MagicMock

from pathlib import Path
from pytest_kubernetes.providers import AClusterManager

logger = logging.getLogger()


class TestBridgeMountStateMachine:
    def test_duplication_by_bridge_mount_install(self, gefyra_crd: AClusterManager):
        from gefyra.bridge_mount_state import GefyraBridgeMount
        from gefyra.bridge_mount_state import GefyraBridgeMountObject

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
            logger=logger,
        )
        assert bridge_mount_machine.requested.is_active
        bridge_mount_machine.prepare()

        gefyra_crd.wait(
            "deployment/" + name + "-gefyra",
            "jsonpath='{.status.readyReplicas}'=1",
            namespace=namespace,
            timeout=60,
        )
        assert bridge_mount_machine.active.is_active

        bridge_mount_machine.terminate()
        gefyra_crd.wait(
            "deployment/" + name + "-gefyra",
            "delete",
            namespace=namespace,
            timeout=60,
        )
        assert bridge_mount_machine.terminated.is_active
