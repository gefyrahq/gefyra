import asyncio, signal

import kopf
import kubernetes as k8s

from gefyra.connection.stowaway import Stowaway
from gefyra.configuration import configuration

from gefyra.connection.stowaway.utils import parse_wg_output


WIREGUARD_RECONCILIATION = 60
custom_object_api = k8s.client.CustomObjectsApi()


async def periodic(interval_sec, coro_name, *args, **kwargs):
    # loop forever
    while True:
        # wait an interval
        await asyncio.sleep(interval_sec)
        # await the target
        await coro_name(*args, **kwargs)


async def read_wireguard_status(logger):
    from gefyra.clientstate import GefyraClientObject, GefyraClient

    try:
        raw_gefyra_clients = custom_object_api.list_namespaced_custom_object(
            group="gefyra.dev",
            version="v1",
            plural="gefyraclients",
            namespace=configuration.NAMESPACE,
        )
    except Exception as e:
        logger.error(f"Could not read clients from Stowaway watcher: {e}")
        return
    else:
        if len(raw_gefyra_clients["items"]) == 0:
            logger.info(
                "Skipping Wireguard connection status on Stowaway: no GefyraClients available"
            )
            return

    # there are some GefyraClients
    stowaway = Stowaway(configuration, logger)
    if not stowaway.ready():
        logger.info(
            "Skipping Wireguard connection status on Stowaway: currently not ready"
        )
        return
    logger.info("Checking Wireguard connection status on Stowaway")
    wg_status = stowaway.read_wireguard_status()
    if not wg_status:
        logger.error(
            "Wireguard connection status was empty. Wireguard probably not working!"
        )
        return
    try:
        wg_data = parse_wg_output(wg_status)
    except Exception as e:
        logger.error(f"Could not parse Wireguard status: {e}")
        return
    else:
        peer_data = wg_data["peers"]
        for body in raw_gefyra_clients["items"]:
            try:
                obj = GefyraClientObject(body)
                client = GefyraClient(obj, configuration, logger)
                if client.active.is_active:
                    try:
                        peer_status = next(
                            filter(
                                lambda p: p["public_key"]
                                == client.data["providerConfig"]["Interface.PublicKey"],
                                peer_data,
                            )
                        )
                    except StopIteration:
                        logger.error(
                            f"Found active GefyraClient '{client.client_name}', which has no Wireguard peer entry. Setting to waiting."
                        )
                        client.disable()
                        continue
                    except KeyError:
                        # there is at least one client which has not yet set the "Interface.PublicKey", probably old
                        pass
                    else:
                        if (
                            "wireguard" in client.data["status"]
                            and peer_status == client.data["status"]["wireguard"]
                        ):
                            continue
                        else:
                            client._patch_object({"status": {"wireguard": peer_status}})
                            # client.post_event(
                            #     reason="GefyraClient connection",
                            #     message="Updated Wireguard status (see .status.wireguard field)",
                            # )
            except Exception as e:
                logger.error(
                    f"Error processing Wireguard status for GefyraClient '{body['metadata']['name']}': {e}"
                )


@kopf.on.startup()
async def register_stowaway_watch(logger, retry, **kwargs) -> None:
    # configure the periodic task
    task = asyncio.create_task(
        periodic(WIREGUARD_RECONCILIATION, read_wireguard_status, logger)
    )

    def shutdown(*args, **kwargs):
        task.cancel()

    signal.signal(signal.SIGINT, shutdown)
