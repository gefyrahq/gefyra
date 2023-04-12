import kopf

from gefyra.clientstate import GefyraClient
from gefyra.configuration import configuration


@kopf.on.create("gefyraclients.gefyra.dev")
@kopf.on.resume("gefyraclients.gefyra.dev")
async def client_created(body, logger, **kwargs):
    client = GefyraClient(configuration, model=body, logger=logger)
    if client.requested.is_active:
        client.create()

