import kopf

from gefyra.bridgestate import GefyraBridge, GefyraBridgeObject
from gefyra.configuration import configuration


@kopf.on.create("gefyrabridges.gefyra.dev")
@kopf.on.resume("gefyrabridges.gefyra.dev")
async def bridge_create(body, logger, **kwargs):
    obj = GefyraBridgeObject(body)
    bridge = GefyraBridge(obj, configuration, logger)
    if bridge.requested.is_active:
        bridge.install()
    if bridge.installing.is_active:
        bridge.install()
    if bridge.installed.is_active:
        bridge.activate()


@kopf.on.delete("gefyrabridges.gefyra.dev")
async def bridge_delete(body, logger, **kwargs):
    obj = GefyraBridgeObject(body)
    bridge = GefyraBridge(obj, configuration, logger)
    if (
        bridge.active.is_active
        or bridge.creating.is_active
        or bridge.removing.is_active
    ):
        bridge.remove()
    if bridge.installed.is_active:
        bridge.restore()
