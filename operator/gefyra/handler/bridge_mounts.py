import kopf

from gefyra.bridge_mount_state import GefyraBridgeMount, GefyraBridgeMountObject
from gefyra.configuration import configuration


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
