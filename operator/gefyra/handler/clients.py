import kopf

from gefyra.clientstate import GefyraClientObject, GefyraClient
from gefyra.configuration import configuration


@kopf.on.create("gefyraclients.gefyra.dev")
@kopf.on.resume("gefyraclients.gefyra.dev")
async def client_created(body, logger, **kwargs):
    obj = GefyraClientObject(body)
    client = GefyraClient(obj, configuration, logger)
    if client.requested.is_active:
        # trigger the state transition
        client.create()
    if client.creating.is_active:
        # actually work on creating the items
        client.create()
    if client.waiting.is_active:
        pass


@kopf.on.field("gefyraclients.gefyra.dev", field="providerParameter")
async def client_connection_changed(body, logger, **kwargs):
    obj = GefyraClientObject(body)
    client = GefyraClient(obj, configuration, logger)
    if client.waiting.is_active:
        # trigger the state transition
        await client.enable()
    if client.enabling.is_active:
        await client.activate()
