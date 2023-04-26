import kopf

from gefyra.clientstate import GefyraClientObject, GefyraClient
from gefyra.configuration import configuration
from statemachine.exceptions import TransitionNotAllowed


@kopf.on.create("gefyraclients.gefyra.dev")
@kopf.on.resume("gefyraclients.gefyra.dev")
async def client_created(body, logger, **kwargs):
    obj = GefyraClientObject(body)
    client = GefyraClient(obj, configuration, logger)
    if client.requested.is_active or client.creating.is_active:
        client.create()
    if client.waiting.is_active:
        pass

# 'providerParameter' activates the client, once set to a provider specific value the
# Gefyra Operator will make the connection available
@kopf.on.field("gefyraclients.gefyra.dev", field="providerParameter")
async def client_connection_changed(new, body, logger, **kwargs):
    obj = GefyraClientObject(body)
    client = GefyraClient(obj, configuration, logger)
    # check if parameters for this connection provider have been added or removed
    if bool(new):
        # activate this connection
        try:
            if client.waiting.is_active:
                client.enable()
            if client.enabling.is_active:
                client.activate() 
        except TransitionNotAllowed as e:
            logger.error(f"TransitionNotAllowed: {e}")
            client.impair()
    else:
        # deactivate this connection
        if client.active.is_active or client.error.is_active:
            # only trigger the state transition
            client.disable()
        if client.disabling.is_active:
            # this is called in case of retry
            client.wait()


@kopf.on.delete("gefyraclients.gefyra.dev")
async def client_deleted(body, logger, **kwargs):
    obj = GefyraClientObject(body)
    client = GefyraClient(obj, configuration, logger)
    client.terminate()
