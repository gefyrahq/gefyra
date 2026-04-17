import os
import asyncio
import signal

import kopf
import kubernetes as k8s

from gefyra.connection.stowaway import Stowaway
from gefyra.configuration import configuration

from gefyra.connection.stowaway.utils import parse_wg_output
from gefyra.connection.stowaway.resources.configmaps import (
    create_stowaway_proxyroute_configmap,
)


WIREGUARD_RECONCILIATION = 60
custom_object_api = k8s.client.CustomObjectsApi()
core_v1_api = k8s.client.CoreV1Api()


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
    if not await stowaway.ready():
        logger.info(
            "Skipping Wireguard connection status on Stowaway: currently not ready"
        )
        return
    logger.info("Checking Wireguard connection status on Stowaway")
    wg_status = await stowaway.read_wireguard_status()
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
                                lambda p: (
                                    p["public_key"]
                                    == client.data["providerConfig"][
                                        "Interface.PublicKey"
                                    ]
                                ),
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
                        if "status" not in client.data:
                            await client._patch_object({"status": {}})
                        if (
                            "wireguard" in client.data["status"]
                            and peer_status == client.data["status"]["wireguard"]
                        ):
                            continue
                        else:
                            await client._patch_object(
                                {"status": {"wireguard": peer_status}}
                            )
                            # client.post_event(
                            #     reason="GefyraClient connection",
                            #     message="Updated Wireguard status (see .status.wireguard field)",
                            # )
            except Exception as e:
                logger.error(
                    f"Error processing Wireguard status for GefyraClient '{body['metadata']['name']}': {e}"
                )


async def reconcile_proxyroutes(logger):
    stowaway = Stowaway(configuration, logger)
    if not await stowaway.ready():
        logger.info("Skipping proxy route status on Stowaway: currently not ready")
        return

    _config = create_stowaway_proxyroute_configmap()
    configmap = await asyncio.to_thread(
        core_v1_api.read_namespaced_config_map,
        _config.metadata.name,
        _config.metadata.namespace,
    )
    routes = configmap.data
    try:
        raw_gefyra_bridges = await asyncio.to_thread(
            custom_object_api.list_namespaced_custom_object,
            group="gefyra.dev",
            version="v1",
            plural="gefyrabridges",
            namespace=configuration.NAMESPACE,
        )
    except Exception as e:
        logger.error(f"Could not list all GefyraBridges: {e}")
        return
    else:
        logger.info("Checking proxy route status on Stowaway")

        if len(raw_gefyra_bridges["items"]) == 0:
            # if we find proxy routes, but there are no bridges -> remove debris
            if routes and len(routes) != 0:
                for _, value in routes.items():
                    stowaway_port = value.split(",")[1]
                    try:
                        await asyncio.to_thread(
                            core_v1_api.delete_namespaced_service,
                            name=f"gefyra-stowaway-proxy-{stowaway_port}",
                            namespace=configuration.NAMESPACE,
                        )
                    except Exception:
                        continue
                configmap.data = {}
                await asyncio.to_thread(
                    core_v1_api.replace_namespaced_config_map,
                    name=configmap.metadata.name,
                    namespace=configmap.metadata.namespace,
                    body=configmap,
                )
            return
        else:
            final_routes = {}
            to_be_removed_svcs = []
            if not routes:
                logger.error(
                    "There are GefyraBridge objects present, but not proxy routes"
                )
                return
            for key, value in routes.items():
                stowaway_port = value.split(",")[1]
                peer = key.rsplit("-", 1)[0]  # client names may contain dashes
                destination_ip = value.split(",")[0].split(":")[0]
                destination_port = value.split(",")[0].split(":")[1]
                for bridge in raw_gefyra_bridges["items"]:
                    logger.warning(f"Delete Me: {bridge}")
                    if (
                        bridge["client"] == peer
                        and bridge["destinationIP"] == destination_ip
                        and str(stowaway_port)
                        in map(
                            lambda x: x.split(":")[1],
                            bridge["clusterEndpoint"].values(),
                        )
                    ):
                        # this bridge corresponds to the route
                        final_routes[key] = value
                        break
                    else:
                        continue
                else:
                    # there was no bridge matched -> route is debris
                    to_be_removed_svcs.append(f"gefyra-stowaway-proxy-{stowaway_port}")
                    logger.warning(
                        f"Could not find a corresponding GefyraBridge ({len(raw_gefyra_bridges['items'])}) for "
                        f"proxy route Peer:{peer}, {destination_ip}, {destination_port} to Stowaway:{stowaway_port}"
                    )

            if len(final_routes) != len(routes):
                logger.warning("Old proxy routes detected, removing them")
                configmap.data = final_routes
                await asyncio.to_thread(
                    core_v1_api.replace_namespaced_config_map,
                    name=configmap.metadata.name,
                    namespace=configmap.metadata.namespace,
                    body=configmap,
                )
                for svc in to_be_removed_svcs:
                    try:
                        logger.info(f"Removing: {svc}")
                        await asyncio.to_thread(
                            core_v1_api.delete_namespaced_service,
                            name=svc,
                            namespace=configuration.NAMESPACE,
                        )
                    except Exception:
                        continue
                stowaway_pod = await stowaway._get_stowaway_pod()
                if stowaway_pod is None:
                    logger.error("No Stowaway Pod found for notification")
                else:
                    await stowaway._notify_stowaway_pod(stowaway_pod.metadata.name)


if os.getenv("OP_MODE", default="Operator").lower() == "operator":

    @kopf.on.startup()
    async def register_stowaway_watch(logger, retry, **kwargs) -> None:
        # configure the periodic task
        wg_task = asyncio.create_task(
            periodic(WIREGUARD_RECONCILIATION, read_wireguard_status, logger)
        )
        proxyroutes_task = asyncio.create_task(
            periodic(WIREGUARD_RECONCILIATION * 5, reconcile_proxyroutes, logger)
        )

        def shutdown(*args, **kwargs):
            wg_task.cancel()
            proxyroutes_task.cancel()

        try:
            signal.signal(signal.SIGINT, shutdown)
        except ValueError:
            # this happens during test runs, we can just pass
            pass
