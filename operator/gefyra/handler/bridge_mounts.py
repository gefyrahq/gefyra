import kubernetes as k8s
import kopf

from gefyra.bridge_mount_state import GefyraBridgeMount, GefyraBridgeMountObject
from gefyra.configuration import configuration

RECONCILIATION_INTERVAL = 30


@kopf.on.create("gefyrabridgemounts.gefyra.dev")
@kopf.on.resume("gefyrabridgemounts.gefyra.dev")
async def bridge_mount_created(body, logger, **kwargs):
    obj = GefyraBridgeMountObject(body)
    bridge_mount = GefyraBridgeMount(obj, configuration, logger)
    if bridge_mount.requested.is_active:
        bridge_mount.prepare()
    if (
        bridge_mount.preparing.is_active
        or bridge_mount.installing.is_active
        or bridge_mount.active.is_active
    ):
        pass


@kopf.on.delete("gefyrabridgemounts.gefyra.dev")
async def client_deleted(body, logger, **kwargs):
    obj = GefyraBridgeMountObject(body)
    bridge_mount = GefyraBridgeMount(obj, configuration, logger)
    bridge_mount.terminate()


@kopf.timer("gefyraclients.gefyra.dev", interval=RECONCILIATION_INTERVAL)
async def client_reconcile(body, logger, **kwargs):
    obj = GefyraBridgeMountObject(body)
    bridge_mount = GefyraBridgeMount(obj, configuration, logger)
    if bridge_mount.should_terminate:
        # terminate this client
        bridge_mount.terminate()
        try:
            bridge_mount.custom_api.delete_namespaced_custom_object(
                namespace=bridge_mount.configuration.NAMESPACE,
                name=bridge_mount.client_name,
                group="gefyra.dev",
                plural="gefyrabridgemounts",
            )
        except k8s.client.ApiException:
            pass

    if not bridge_mount.is_intact:
        bridge_mount.impair()
        bridge_mount.restore()
