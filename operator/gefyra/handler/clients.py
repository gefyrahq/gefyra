import asyncio

import click
import kopf
import kubernetes as k8s

from gefyra.clientstate import GefyraClientObject, GefyraClient
from gefyra.configuration import configuration
from statemachine.exceptions import TransitionNotAllowed


@kopf.on.create("gefyraclients.gefyra.dev")
@kopf.on.resume("gefyraclients.gefyra.dev")
async def client_created(body, logger, **kwargs):
    obj = GefyraClientObject(body)
    client = GefyraClient(
        obj, configuration, logger, initial=obj.state
    )  # Pass initial state
    if client.requested.is_active or client.creating.is_active:
        await client.create()  # Await


# 'providerParameter' activates the client, once set to a provider specific value the
# Gefyra Operator will make the connection available
@kopf.on.field("gefyraclients.gefyra.dev", field="providerParameter")
async def client_connection_changed(new, body, logger, **kwargs):
    obj = GefyraClientObject(body)
    client = GefyraClient(
        obj, configuration, logger, initial=obj.state
    )  # Pass initial state
    # check if parameters for this connection provider have been added or removed
    logger.info(f"Client is: {client.current_state}")
    if bool(new):
        # activate this connection
        try:
            if client.waiting.is_active:
                await client.enable()  # Await
            if client.enabling.is_active:
                await client.activate()  # Await
        except TransitionNotAllowed as e:
            logger.error(f"TransitionNotAllowed: {e}")
            await client.impair()  # Await
        except k8s.client.exceptions.ApiException as e:
            logger.error(f"ApiException: {e}")
            if e.status == 500:
                raise kopf.TemporaryError(
                    f"Could not activate connection: {e}, \nClient is {client.current_state}",
                    delay=1,
                )
    else:
        # deactivate this connection
        if client.active.is_active or client.error.is_active:
            # only trigger the state transition
            await client.disable()  # Await
        if client.disabling.is_active:
            # this is called in case of retry
            await client.wait()  # Await
        await client._patch_object({"status": {"wireguard": None}})  # Await


@kopf.on.delete("gefyraclients.gefyra.dev")
async def client_deleted(body, logger, **kwargs):
    obj = GefyraClientObject(body)
    client = GefyraClient(
        obj, configuration, logger, initial=obj.state
    )  # Pass initial state
    await client.terminate()


# this is a workaround to get the --dev flag from the CLI for testing
# https://kopf.readthedocs.io/en/stable/cli/#development-mode
try:
    _ctx = click.get_current_context()
    if "priority" in _ctx.params and _ctx.params["priority"] == 666:
        RECONCILIATION_INTERVAL = 2
    else:
        RECONCILIATION_INTERVAL = 60
except RuntimeError:
    # this module is not imported via kopf CLI
    RECONCILIATION_INTERVAL = 2


@kopf.timer("gefyraclients.gefyra.dev", interval=RECONCILIATION_INTERVAL)
async def client_reconcile(body, logger, **kwargs):
    obj = GefyraClientObject(body)
    client = GefyraClient(
        obj, configuration, logger, initial=obj.state
    )  # Pass initial state
    if await client.should_terminate():  # Await
        # terminate this client
        await client.terminate()  # Await
        try:
            await asyncio.to_thread(
                client.custom_api.delete_namespaced_custom_object,
                namespace=client.configuration.NAMESPACE,
                name=client.client_name,
                group="gefyra.dev",
                plural="gefyraclients",
                version="v1",
            )
        except k8s.client.ApiException:
            pass
    if await client.should_disable():  # Await
        await client.disable()  # Await
