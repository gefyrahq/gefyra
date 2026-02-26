from asyncio import sleep

import kopf

from gefyra.bridgestate import GefyraBridge, GefyraBridgeObject
from gefyra.configuration import configuration


RECONCILIATION_INTERVAL = 10


@kopf.on.create("gefyrabridges.gefyra.dev")
@kopf.on.resume("gefyrabridges.gefyra.dev")
async def bridge_create(body, logger, **kwargs):
    obj = GefyraBridgeObject(body)
    bridge = GefyraBridge(
        obj, configuration, logger, initial=obj.state
    )  # Pass initial state
    if bridge.requested.is_active:
        await bridge.install()
    if bridge.installing.is_active:
        await bridge.install()
    if bridge.installed.is_active:
        await bridge.activate()


@kopf.on.field("gefyrabridges.gefyra.dev", field="destinationIP")
async def update_bridge_destination(body, logger, old, new, **kwargs):
    obj = GefyraBridgeObject(body)
    bridge = GefyraBridge(
        obj, configuration, logger, initial=obj.state
    )  # Pass initial state
    if not old:
        return
    if bridge.active.is_active:
        logger.warn(f"Updating destinationIP for this GefyraBridge: {bridge}")
        await bridge.handle_proxyroute_teardown(old)  # Await
        await bridge.send("restore")  # Await
        await bridge.send("activate")  # Await
    else:
        # TODO handle these cases
        logger.warn(
            f"GefyraBridge {bridge} is not ACTIVE, but destinationIP has been changed."
        )


@kopf.on.delete("gefyrabridges.gefyra.dev")
async def bridge_delete(body, logger, **kwargs):
    obj = GefyraBridgeObject(body)
    bridge = GefyraBridge(
        obj, configuration, logger, initial=obj.state
    )  # Pass initial state
    try:
        await bridge.send("remove")
    except Exception as e:
        logger.error(f"Unexpected error removing this GefyraBridge: {e}")
