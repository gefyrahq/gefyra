import logging
import os
from asyncio import sleep
from typing import Awaitable

import kubernetes as k8s

from gefyra.configuration import configuration
from gefyra.utils import stream_copy_from_pod, read_wireguard_config
from gefyra.resources.secrets import create_wireguard_connection_secret

logger = logging.getLogger("gefyra.stowaway")

STOWAWAY_POD = None


async def get_wireguard_connection_details(aw_stowaway_ready: Awaitable):
    stowaway_ready = await aw_stowaway_ready
    if not stowaway_ready:
        # this is a critical error; probably remove the complete Gefyra session
        return
    core_v1_api = k8s.client.CoreV1Api()

    stowaway_pod = core_v1_api.list_namespaced_pod(
        configuration.NAMESPACE, label_selector="app=stowaway"
    )
    if len(stowaway_pod.items) != 1:
        logger.error(f"Stowaway Pods: {len(stowaway_pod.items)} which is != 1")
        # this is a critical error; there is no pod or more than one pod available (from older releases)
        return

    logger.info(
        f"Copy Peer1 connection details from Pod "
        f"{stowaway_pod.items[0].metadata.name}:{configuration.STOWAWAY_PEER_CONFIG_PATH}"
    )
    tmpfile_location = "/tmp/peer1.conf"
    stream_copy_from_pod(
        stowaway_pod.items[0].metadata.name,
        configuration.NAMESPACE,
        configuration.STOWAWAY_PEER_CONFIG_PATH,
        tmpfile_location,
    )

    # Wireguard config is unfortunately no valid TOML
    with open(tmpfile_location, "r") as f:
        peer1_connection_details_raw = f.read()
    os.remove(tmpfile_location)

    logger.info("Creating Cargo connection secret")
    peer1_connection_details = read_wireguard_config(peer1_connection_details_raw)
    try:
        secret = create_wireguard_connection_secret(peer1_connection_details)
    except Exception as e:
        logger.exception(e)
    try:
        core_v1_api.create_namespaced_secret(
            body=secret, namespace=configuration.NAMESPACE
        )
        logger.info("Cargo connection secret created")
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            # the connection secret deployment already exist
            logger.warning(
                "Cargo connection secret exists, now patching it with current data"
            )
            core_v1_api.patch_namespaced_secret(
                name=secret.metadata.name,
                body=secret,
                namespace=configuration.NAMESPACE,
            )
            logger.info("Cargo connection secret patched")
        else:
            logger.exception(e)
            raise e
    except Exception as e:
        logger.exception(e)
