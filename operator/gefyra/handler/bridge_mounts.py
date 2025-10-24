import kubernetes as k8s
import kopf
from statemachine.exceptions import TransitionNotAllowed

from gefyra.bridge_mount_state import GefyraBridgeMount, GefyraBridgeMountObject
from gefyra.configuration import configuration

RECONCILIATION_INTERVAL = 10


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
async def bridgemount_deleted(body, logger, **kwargs):
    obj = GefyraBridgeMountObject(body)
    bridge_mount = GefyraBridgeMount(obj, configuration, logger)
    bridge_mount.terminate()


@kopf.timer("gefyrabridgemounts.gefyra.dev", interval=RECONCILIATION_INTERVAL)
async def bridge_mount_reconcile(body, logger, **kwargs):
    obj = GefyraBridgeMountObject(body)
    bridge_mount = GefyraBridgeMount(obj, configuration, logger)
    logger.info("Reconciliation for GefyraBridgeMount.")
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
            return
        except k8s.client.ApiException:
            pass

    try:
        if bridge_mount.requested.is_active:
            bridge_mount.prepare()
        elif bridge_mount.preparing.is_active:
            bridge_mount.install()
        elif bridge_mount.installing.is_active:
            bridge_mount.install()
        # TODO if Error is recoverable at all
        # elif bridge_mount.error.is_active:
        #    bridge_mount.restore()
        elif bridge_mount.restoring.is_active:
            bridge_mount.restore()
        elif bridge_mount.active.is_active:
            # check if all is good
            if not bridge_mount.is_intact:
                bridge_mount.restore()
    # this happens when either the transition from x to y is not allowed
    # or when the condition for the transition is not fulfilled.
    except TransitionNotAllowed as e:
        retry_delay = 3
        raise kopf.TemporaryError(
            f"Transition not allowed: {e}. Retrying in {retry_delay}s.",
            delay=retry_delay,
        )
