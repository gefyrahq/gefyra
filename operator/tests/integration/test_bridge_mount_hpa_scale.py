"""
Integration tests covering HPA duplication for shadow deployments (GO-1030).

When a GefyraBridgeMount is created and the original workload has an HPA, the
operator must clone the HPA, retarget it to the shadow workload and clean up
the duplicate when the mount is removed. Workloads without an HPA must still
mount cleanly.
"""

import logging
from pathlib import Path
from time import sleep
from unittest.mock import MagicMock

from pytest_kubernetes.providers import AClusterManager
from statemachine.exceptions import TransitionNotAllowed

from gefyra.bridge_mount.utils import generate_duplicate_hpa_name
from gefyra.configuration import OperatorConfiguration

logger = logging.getLogger()
logger.addHandler(logging.NullHandler())


NGINX_FIXTURE = str(
    Path(Path(__file__).parent.parent, "fixtures/nginx.yaml").absolute()
)
HPA_FIXTURE = str(
    Path(Path(__file__).parent.parent, "fixtures/nginx_hpa.yaml").absolute()
)


def _make_bridge_mount(name: str, namespace: str):
    from gefyra.bridge_mount_state import GefyraBridgeMount, GefyraBridgeMountObject

    obj = GefyraBridgeMountObject(
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
    obj._write_state = MagicMock()
    return GefyraBridgeMount(
        model=obj,
        configuration=OperatorConfiguration(),
        logger=logger,
        initial="REQUESTED",
    )


async def _drive_to_active(bm) -> None:
    """Walk the state machine forward until ACTIVE or retries exhausted."""
    retries = 120
    while retries > 0:
        provider = bm.bridge_mount_provider
        for attr in list(vars(provider)):
            if attr.startswith("get_pods_workload_cache-") or attr.startswith(
                "_get_workload_cache-"
            ):
                delattr(provider, attr)
        try:
            if bm.requested.is_active:
                await bm.arrange()
            elif bm.preparing.is_active:
                await bm.install()
            elif bm.installing.is_active:
                await bm.install()
            elif bm.active.is_active:
                return
        except TransitionNotAllowed:
            retries -= 1
        except Exception:
            retries -= 1
        sleep(3)


class TestBridgeMountHPADuplication:
    async def test_mount_duplicates_hpa(self, gefyra_crd: AClusterManager):
        """With an HPA on the original deployment, the operator clones it to
        target the shadow deployment. The original HPA stays untouched."""
        name = "nginx-deployment"
        namespace = "default"
        original_hpa = "nginx-deployment-hpa"
        duplicated_hpa = generate_duplicate_hpa_name(original_hpa)

        gefyra_crd.apply(NGINX_FIXTURE)
        gefyra_crd.wait(
            "deployment/" + name,
            "jsonpath='{.status.readyReplicas}'=1",
            namespace=namespace,
            timeout=120,
        )
        gefyra_crd.apply(HPA_FIXTURE)

        bm = _make_bridge_mount(name, namespace)
        try:
            await _drive_to_active(bm)
            assert bm.active.is_active, (
                f"BridgeMount should be ACTIVE but is {bm.current_state.value}"
            )

            # Duplicated HPA exists and points at the shadow workload.
            duplicated = gefyra_crd.kubectl(
                [
                    "-n",
                    namespace,
                    "get",
                    "hpa",
                    duplicated_hpa,
                    "-o",
                    "json",
                ]
            )
            assert (
                duplicated["spec"]["scaleTargetRef"]["name"]
                == name + "-gefyra"
            )
            assert duplicated["spec"]["scaleTargetRef"]["kind"] == "Deployment"

            # Original HPA still targets the original deployment.
            original = gefyra_crd.kubectl(
                ["-n", namespace, "get", "hpa", original_hpa, "-o", "json"]
            )
            assert original["spec"]["scaleTargetRef"]["name"] == name
        finally:
            await bm.terminate()
            gefyra_crd.wait(
                "deployment/" + name + "-gefyra",
                "delete",
                namespace=namespace,
                timeout=60,
            )
            gefyra_crd.wait(
                "hpa/" + duplicated_hpa,
                "delete",
                namespace=namespace,
                timeout=60,
            )
            # Original HPA must still be present.
            gefyra_crd.kubectl(
                ["-n", namespace, "get", "hpa", original_hpa]
            )
            gefyra_crd.kubectl(
                ["-n", namespace, "delete", "hpa", original_hpa],
                as_dict=False,
            )
        assert bm.terminated.is_active

    async def test_mount_without_hpa_succeeds(self, gefyra_crd: AClusterManager):
        """No HPA on the original → mount still reaches ACTIVE, no shadow HPA
        is created, no errors raised."""
        name = "nginx-deployment"
        namespace = "default"

        gefyra_crd.apply(NGINX_FIXTURE)
        gefyra_crd.wait(
            "deployment/" + name,
            "jsonpath='{.status.readyReplicas}'=1",
            namespace=namespace,
            timeout=120,
        )

        bm = _make_bridge_mount(name, namespace)
        try:
            await _drive_to_active(bm)
            assert bm.active.is_active

            hpas = gefyra_crd.kubectl(
                ["-n", namespace, "get", "hpa", "-o", "json"]
            )
            shadow_hpa_names = [
                item["metadata"]["name"]
                for item in hpas.get("items", [])
                if item["metadata"]["name"].endswith("-gefyra")
            ]
            assert shadow_hpa_names == []
        finally:
            await bm.terminate()
            gefyra_crd.wait(
                "deployment/" + name + "-gefyra",
                "delete",
                namespace=namespace,
                timeout=60,
            )
        assert bm.terminated.is_active
