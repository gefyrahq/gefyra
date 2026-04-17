"""
Integration test: BridgeMount must reach ACTIVE even when the original
deployment is scaled (simulating HPA) during the PREPARING/INSTALLING phase.

Without the fix, the mount would loop forever in PREPARING because
prepared() always sees a replica count mismatch.
"""

import logging
from time import sleep
from unittest.mock import MagicMock

from pathlib import Path
import pytest
from pytest_kubernetes.providers import AClusterManager
from statemachine.exceptions import TransitionNotAllowed

from gefyra.configuration import OperatorConfiguration

logger = logging.getLogger()
logger.addHandler(logging.NullHandler())


class TestBridgeMountHPAScale:
    async def test_mount_reaches_active_despite_scaling(
        self, gefyra_crd: AClusterManager
    ):
        """Simulate HPA: scale original deployment while mount is installing.

        1. Deploy nginx with 1 replica
        2. Start BridgeMount state machine
        3. After shadow is created (PREPARING), scale original to 3
        4. Verify the mount still reaches ACTIVE (shadow gets scaled to match)
        """
        from gefyra.bridge_mount_state import GefyraBridgeMount, GefyraBridgeMountObject

        file_path = str(
            Path(Path(__file__).parent.parent, "fixtures/nginx_hpa.yaml").absolute()
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
                "apiVersion": "gefyra.dev/v1",
                "metadata": {
                    "name": name,
                    "namespace": namespace,
                    "uid": "hpa-test-uid",
                    "resourceVersion": "123456",
                },
                "kind": "gefyrabridgemount",
                "state": "REQUESTED",
                "targetNamespace": namespace,
                "target": "deploy/" + name,
                "targetContainer": "nginx",
                "provider": "carrier2mount",
            }
        )
        bridge_mount_object._write_state = MagicMock()
        configuration = OperatorConfiguration()

        bm = GefyraBridgeMount(
            model=bridge_mount_object,
            configuration=configuration,
            logger=logger,
            initial="REQUESTED",
        )
        assert bm.requested.is_active

        scaled = False
        retries = 120
        while retries > 0:
            # Clear the provider's pod cache to simulate the real handler
            # which creates a fresh provider instance on each invocation.
            provider = bm.bridge_mount_provider
            for attr in list(vars(provider)):
                if attr.startswith("get_pods_workload_cache-") or attr.startswith(
                    "_get_workload_cache-"
                ):
                    delattr(provider, attr)

            print(bm)
            try:
                if bm.requested.is_active:
                    await bm.arrange()
                elif bm.preparing.is_active:
                    # Scale original deployment after shadow was created
                    if not scaled:
                        logger.info(
                            "Scaling original deployment to 3 replicas to simulate HPA"
                        )
                        gefyra_crd.kubectl(
                            [
                                "-n",
                                namespace,
                                "scale",
                                "deployment/" + name,
                                "--replicas=3",
                            ],
                            as_dict=False,
                        )
                        gefyra_crd.wait(
                            "deployment/" + name,
                            "jsonpath='{.status.readyReplicas}'=3",
                            namespace=namespace,
                            timeout=120,
                        )
                        scaled = True
                        logger.info("Original deployment scaled to 3")
                    await bm.install()
                elif bm.installing.is_active:
                    # Mirror the real handler: call install() (self-transition)
                    # which triggers on_install → carrier install → activate
                    await bm.install()
                elif bm.active.is_active:
                    break
            except TransitionNotAllowed:
                retries -= 1
            except Exception:
                print(f"TemporaryError {retries}")
                retries -= 1

            sleep(3)

        assert bm.active.is_active, (
            f"BridgeMount should be ACTIVE but is "
            f"{bm.current_state.value} after scaling"
        )

        res = gefyra_crd.kubectl(
            ["-n", namespace, "get", "hpa/" + name + "-gefyra"],
            as_dict=True,
        )

        assert res["kind"] == "HorizontalPodAutoscaler", (
            "HPA resource for shadow deployment should exist but got error"
        )

        gefyra_crd.wait(
            "deployment/" + name + "-gefyra",
            "jsonpath='{.status.readyReplicas}'=3",
            namespace=namespace,
            timeout=120,
        )

        # Cleanup
        await bm.terminate()
        gefyra_crd.wait(
            "deployment/" + name + "-gefyra",
            "delete",
            namespace=namespace,
            timeout=60,
        )
        assert bm.terminated.is_active
        with pytest.raises(RuntimeError) as exc_info:
            gefyra_crd.kubectl(
                ["-n", namespace, "get", "hpa/" + name + "-gefyra"],
                as_dict=True,
            )

        assert (
            'horizontalpodautoscalers.autoscaling "nginx-deployment-gefyra" not found'
            in str(exc_info.value)
        ), "HPA resource for shadow deployment should not exist after termination"

        gefyra_crd.kubectl(["-n", namespace, "delete", "-f", file_path])
