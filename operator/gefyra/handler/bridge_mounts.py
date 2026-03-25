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
            logger.info("Staring up a new GefyraBridgeMount")
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
        logger.warning(f"Transition not allowed: {e}. Retrying in {retry_delay}s.")
        raise kopf.TemporaryError(
            f"Transition not allowed. Retrying in {retry_delay}s.",
            delay=retry_delay,
        )


@kopf.on.delete("gefyrabridgemounts.gefyra.dev")
async def bridgemount_deleted(body, logger, **kwargs):
    obj = GefyraBridgeMountObject(body)
    bridge_mount = GefyraBridgeMount(obj, configuration, logger, initial=obj.state)
    logger.info(f"Deleting {bridge_mount}")
    if not bridge_mount.terminated.is_active:
        await bridge_mount.terminate()


def _try_delete_cr(bridge_mount: GefyraBridgeMount, logger) -> bool:
    """Best-effort deletion of the GefyraBridgeMount CR.

    Swallows 404 (already gone) but logs other errors so that the
    reconciliation loop retries on the next tick.

    :return: True if the CR was deleted (or was already gone), False on error.
    """
    try:
        bridge_mount.custom_api.delete_namespaced_custom_object(
            namespace=bridge_mount.configuration.NAMESPACE,
            name=bridge_mount.object_name,
            group="gefyra.dev",
            version="v1",
            plural="gefyrabridgemounts",
        )
        return True
    except k8s.client.ApiException as e:
        if e.status == 404:
            return True  # already gone
        logger.warning(
            f"Failed to delete GefyraBridgeMount CR "
            f"'{bridge_mount.object_name}': {e}. Will retry."
        )
        return False


@kopf.timer(
    "gefyrabridgemounts.gefyra.dev",
    interval=RECONCILIATION_INTERVAL,
)
async def bridge_mount_reconcile(body, logger, **kwargs):
    """
    Periodic reconciliation for GefyraBridgeMount resources.

    Runs every ``RECONCILIATION_INTERVAL`` seconds for all mounts.

    For each reconciliation tick the handler:

    1. For TERMINATED mounts: retries CR deletion if the object was not
       cleaned up previously (e.g. due to a transient API error). Skips
       all other logic once terminated.
    2. Checks ``should_terminate`` (sunset expiry) — terminates + deletes if true.
    3. For MISSING mounts: checks if the target has reappeared (auto-recover)
       or if the grace period has expired (terminate + delete).
    4. For all other operational states: checks ``target_exists`` before
       proceeding with the normal state progression. If the target is gone,
       transitions to MISSING immediately.
    5. For ACTIVE mounts: additionally checks ``is_intact`` and transitions
       to RESTORING if the Carrier2 installation has drifted.
    """
    obj = GefyraBridgeMountObject(body)
    bridge_mount = GefyraBridgeMount(
        obj, configuration, logger, initial=obj.state
    )  # Pass initial state
    if not bridge_mount.completed_transition(GefyraBridgeMount.active.value):
        logger.info(
            f"Skipping reconciliation for GefyraBridgeMount '{bridge_mount.object_name}' (transition to ACTIVE not completed)"
        )
        return
    logger.info(f"Reconciliation for GefyraBridgeMount: {obj}")

    # TERMINATED objects: retry CR deletion, then skip all other logic.
    if bridge_mount.terminated.is_active:
        _try_delete_cr(bridge_mount, logger)
        return

    if await bridge_mount.should_terminate:
        await bridge_mount.terminate()
        _try_delete_cr(bridge_mount, logger)
        return

    try:
        if bridge_mount.missing.is_active:
            if await bridge_mount.target_exists:
                logger.info(
                    f"Target for GefyraBridgeMount '{bridge_mount.object_name}' "
                    "has reappeared. Recovering."
                )
                await bridge_mount.recover()
            elif bridge_mount.missing_grace_period_expired:
                logger.warning(
                    f"Grace period expired for GefyraBridgeMount "
                    f"'{bridge_mount.object_name}'. Terminating."
                )
                await bridge_mount.terminate()
                _try_delete_cr(bridge_mount, logger)
            else:
                logger.info(
                    f"GefyraBridgeMount '{bridge_mount.object_name}' target still "
                    f"missing. Waiting for grace period "
                    f"({bridge_mount.missing_grace_period}s)."
                )
        else:
            # For all operational states, check target existence once.
            if not await bridge_mount.target_exists:
                await bridge_mount.mark_missing()
            else:
                if bridge_mount.requested.is_active:
                    await bridge_mount.arrange()
                elif bridge_mount.preparing.is_active:
                    await bridge_mount.install()
                elif bridge_mount.installing.is_active:
                    await bridge_mount.install()
                elif bridge_mount.error.is_active:
                    await bridge_mount.send("restore")
                elif bridge_mount.restoring.is_active:
                    await bridge_mount.send("restore")
                elif bridge_mount.active.is_active:
                    if not await bridge_mount.is_intact:
                        logger.warning(
                            "GefyraBridgeMount is impaired. Transitioning to restoring state."
                        )
                        await bridge_mount.send("restore")
    # this happens when either the transition from x to y is not allowed
    # or when the condition for the transition is not fulfilled.
    except TransitionNotAllowed as e:
        retry_delay = 15
        logger.warning(f"Transition not allowed: {e}. Retrying in {retry_delay}s.")
        raise kopf.TemporaryError(
            f"Transition not allowed. Retrying in {retry_delay}s.",
            delay=retry_delay,
        )
