import logging
from time import sleep
from unittest.mock import MagicMock

from pathlib import Path
from kopf import TemporaryError
from pytest_kubernetes.providers import AClusterManager
from statemachine.exceptions import TransitionNotAllowed

from gefyra.configuration import OperatorConfiguration

logger = logging.getLogger()


class TestBridgeMountStateMachine:
    def test_a_duplication_by_bridge_mount(self, gefyra_crd: AClusterManager):
        from gefyra.bridge_mount_state import GefyraBridgeMount
        from gefyra.bridge_mount_state import GefyraBridgeMountObject

        file_path = str(
            Path(Path(__file__).parent.parent, "fixtures/nginx.yaml").absolute()
        )
        gefyra_crd.apply(file_path)

        name = "nginx-deployment"
        namespace = "default"

        gefyra_crd.wait(
            "deployment/" + name,
            "jsonpath='{.status.readyReplicas}'=1",
            namespace=namespace,
            timeout=120,
        )

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
        configuration = OperatorConfiguration()

        bridge_mount_machine = GefyraBridgeMount(
            model=bridge_mount_object,
            configuration=configuration,
            logger=logger,
        )
        assert bridge_mount_machine.requested.is_active
        retries = 20
        while retries > 0:
            print(bridge_mount_machine.current_state)
            try:
                if bridge_mount_machine.preparing.is_active:
                    try:
                        bridge_mount_machine.install()
                    except (
                        Exception
                    ):  #  Catch Temporary 'Cannot install Gefyra Carrier2 on pods ...'
                        pass
                elif bridge_mount_machine.requested.is_active:
                    bridge_mount_machine.prepare()
                elif bridge_mount_machine.installing.is_active:
                    bridge_mount_machine.activate()
                else:
                    break
            except TransitionNotAllowed:
                retries -= 1

            sleep(2)

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
