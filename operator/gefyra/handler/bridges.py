import kopf

from gefyra.bridgestate import GefyraBridge, GefyraBridgeObject
from gefyra.configuration import configuration


@kopf.on.create("gefyrabridges.gefyra.dev")
@kopf.on.resume("gefyrabridges.gefyra.dev")
async def client_created(body, logger, **kwargs):
    obj = GefyraBridgeObject(body)
    bridge = GefyraBridge(obj, configuration, logger)
    if bridge.requested.is_active:
        bridge.install()
    if bridge.installing.is_active:
        bridge.install()
    if bridge.installed.is_active:
        bridge.activate()
