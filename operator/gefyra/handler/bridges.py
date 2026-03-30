import asyncio

import kopf

from gefyra.bridgestate import GefyraBridge, GefyraBridgeObject
from gefyra.configuration import configuration


RECONCILIATION_INTERVAL = 60

# A simple registry for locks based on resource UID or name
locks = {}


async def get_lock(name):
    if name not in locks:
        locks[name] = asyncio.Lock()
    return locks[name]


@kopf.on.create("gefyrabridges.gefyra.dev")
@kopf.on.resume("gefyrabridges.gefyra.dev")
async def bridge_create(body, logger, namespace, name, **kwargs):
    obj = GefyraBridgeObject(body)
    bridge = GefyraBridge(
        obj, configuration, logger, initial=obj.state
    )  # Pass initial state

    key = bridge.data["target"]
    lock = await get_lock(key)

    async with lock:
        if bridge.requested.is_active:
            await bridge.install()
        if bridge.installing.is_active:
            await bridge.install()
        if bridge.installed.is_active:
            await bridge.activate()


@kopf.on.field("gefyrabridges.gefyra.dev", field="destinationIP")
async def update_bridge_destination(body, logger, namespace, name, old, new, **kwargs):
    obj = GefyraBridgeObject(body)
    bridge = GefyraBridge(
        obj, configuration, logger, initial=obj.state
    )  # Pass initial state

    key = bridge.data["target"]
    lock = await get_lock(key)
    if bridge.active.is_active and old:
        async with lock:
            logger.warn(f"Updating destinationIP for this GefyraBridge: {bridge}")
            await bridge.handle_proxyroute_teardown(old)
            await bridge.restore()
            if bridge.installed.is_active:
                await bridge.activate()


# @kopf.timer(
#     "gefyrabridges.gefyra.dev",
#     interval=RECONCILIATION_INTERVAL,
# )
# async def bridge_reconcile(body, logger, **kwargs):
#     obj = GefyraBridgeObject(body)
#     bridge = GefyraBridge(
#         obj, configuration, logger, initial=obj.state
#     )  # Pass initial state

#     if not bridge.completed_transition(GefyraBridge.active.value):
#         logger.info(
#             f"Skipping reconciliation for GefyraBridge '{bridge.object_name}' (transition to ACTIVE not completed)"
#         )
#         return
#     logger.info(f"Reconciliation for GefyraBridge: {obj}")

#     key = bridge.data["target"]
#     lock = await get_lock(key)
#     async with lock:
#         try:
#             await bridge.send("terminate")
#         except Exception as e:
#             logger.error(f"Unexpected error removing this GefyraBridge: {e}")


@kopf.on.delete("gefyrabridges.gefyra.dev")
async def bridge_delete(body, logger, namespace, name, **kwargs):
    obj = GefyraBridgeObject(body)
    bridge = GefyraBridge(
        obj, configuration, logger, initial=obj.state
    )  # Pass initial state

    key = bridge.data["target"]
    lock = await get_lock(key)
    async with lock:
        try:
            await bridge.send("terminate")
        except Exception as e:
            logger.error(f"Unexpected error removing this GefyraBridge: {e}")
