import asyncio

import kubernetes as k8s
import kopf
from statemachine.exceptions import TransitionNotAllowed

from gefyra.bridge_mount_state import GefyraBridgeMount, GefyraBridgeMountObject
from gefyra.configuration import configuration

RECONCILIATION_INTERVAL = 60


@kopf.on.create("gefyrabridgemounts.gefyra.dev")
@kopf.on.resume("gefyrabridgemounts.gefyra.dev")
async def bridge_mount_created(body, logger, **kwargs):
    obj = GefyraBridgeMountObject(body)
    bridge_mount = GefyraBridgeMount(
        obj, configuration, logger, initial=obj.state
    )  # Pass initial state

    try:
        if bridge_mount.requested.is_active:
            logger.info(f"Staring up a new GefyraBridgeMount")
            await bridge_mount.arrange()
        if bridge_mount.preparing.is_active:
            await bridge_mount.install()
        if bridge_mount.installing.is_active:
            await bridge_mount.install()
        if bridge_mount.error.is_active:
            await bridge_mount.send("restore")  # Await
        if bridge_mount.restoring.is_active:
            await bridge_mount.send("restore")  # Await
    # this happens when either the transition from x to y is not allowed
    # or when the condition for the transition is not fulfilled.
    except TransitionNotAllowed as e:
        retry_delay = 15
        raise kopf.TemporaryError(
            f"Transition not allowed: {e}. Retrying in {retry_delay}s.",
            delay=retry_delay,
        )


@kopf.on.delete("gefyrabridgemounts.gefyra.dev")
async def bridgemount_deleted(body, logger, **kwargs):
    obj = GefyraBridgeMountObject(body)
    bridge_mount = GefyraBridgeMount(obj, configuration, logger, initial=obj.state)
    logger.info(f"Deleting {bridge_mount}")
    if not bridge_mount.terminated.is_active:
        await bridge_mount.terminate()


# @kopf.timer("gefyrabridgemounts.gefyra.dev", interval=RECONCILIATION_INTERVAL)
# async def bridge_mount_reconcile(body, logger, **kwargs):
#     obj = GefyraBridgeMountObject(body)
#     bridge_mount = GefyraBridgeMount(obj, configuration, logger, initial=obj.state) # Pass initial state
#     logger.info(f"Reconciliation for GefyraBridgeMount: {obj}")
#     if await bridge_mount.should_terminate:
#         # terminate this client
#         await bridge_mount.terminate()
#         try:
#             await asyncio.to_thread(bridge_mount.custom_api.delete_namespaced_custom_object,
#                 namespace=bridge_mount.configuration.NAMESPACE,
#                 name=bridge_mount.client_name,
#                 group="gefyra.dev",
#                 plural="gefyrabridgemounts",
#             )
#         except k8s.client.ApiException:
#             pass

#     try:
#         if bridge_mount.requested.is_active:
#             await bridge_mount.arrange()
#         elif bridge_mount.preparing.is_active:
#             await bridge_mount.install()
#         elif bridge_mount.installing.is_active:
#             await bridge_mount.install() # Await
#         elif bridge_mount.error.is_active:
#             await bridge_mount.send("restore") # Await
#         elif bridge_mount.restoring.is_active:
#             await bridge_mount.send("restore") # Await
#         elif bridge_mount.active.is_active:
#             # check if all is good
#             if not await bridge_mount.is_intact: # Await
#                 logger.warning(
#                     "GefyraBridgeMount is impaired. Transitioning to restoring state."
#                 )
#                 await bridge_mount.send("restore")
#     # this happens when either the transition from x to y is not allowed
#     # or when the condition for the transition is not fulfilled.
#     except TransitionNotAllowed as e:
#         retry_delay = 15
#         raise kopf.TemporaryError(
#             f"Transition not allowed: {e}. Retrying in {retry_delay}s.",
#             delay=retry_delay,
#         )
