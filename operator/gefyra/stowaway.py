import logging
import os
from asyncio import sleep
from typing import Awaitable

import kubernetes as k8s

from gefyra.configuration import configuration
from gefyra.resources.secrets import create_wireguard_connection_secret
from gefyra.utils import stream_copy_from_pod, read_wireguard_config

logger = logging.getLogger("gefyra")

STOWAWAY_POD = None


async def check_stowaway_ready(stowaway_deployment: k8s.client.V1Deployment):
    global STOWAWAY_POD
    app = k8s.client.AppsV1Api()
    core_v1_api = k8s.client.CoreV1Api()

    i = 0
    dep = app.read_namespaced_deployment(name=stowaway_deployment.metadata.name, namespace=configuration.NAMESPACE)
    # a primitive timeout 1 minute
    while i <= configuration.STOWAWAY_STARTUP_TIMEOUT:
        s = dep.status
        if (s.updated_replicas == dep.spec.replicas and
                s.replicas == dep.spec.replicas and
                s.available_replicas == dep.spec.replicas and
                s.observed_generation >= dep.metadata.generation):

            stowaway_pod = core_v1_api.list_namespaced_pod(configuration.NAMESPACE, label_selector="app=stowaway")
            if len(stowaway_pod.items) != 1:
                logger.warning(f"Stowaway not yet ready, Pods: {len(stowaway_pod.items)} which is != 1")
                await sleep(1)
                continue
            STOWAWAY_POD = stowaway_pod.items[0].metadata.name
            logger.info(f"Stowaway ready: {STOWAWAY_POD}")
            return True
        else:
            logger.info(f"Waiting for Stowaway to become ready")
            await sleep(1)
        i += 1
        dep = app.read_namespaced_deployment(name=stowaway_deployment.metadata.name, namespace=configuration.NAMESPACE)
    # reached this in an error case a) timout (build took too long) or b) build could not be successfully executed
    logger.error("Stowaway error: Stowaway did not become ready")
    return False


async def get_wireguard_connection_details(aw_stowaway_ready: Awaitable):
    stowaway_ready = await aw_stowaway_ready
    if not stowaway_ready:
        # this is a critical error; probably remove the complete Gefyra session
        return
    core_v1_api = k8s.client.CoreV1Api()

    stowaway_pod = core_v1_api.list_namespaced_pod(configuration.NAMESPACE, label_selector="app=stowaway")
    if len(stowaway_pod.items) != 1:
        logger.error(f"Stowaway Pods: {len(stowaway_pod.items)} which is != 1")
        # this is a critical error; there is no pod or more than one pod available (from older releases)
        return

    logger.info(f"Copy Peer1 connection details from Pod "
                f"{stowaway_pod.items[0].metadata.name}:{configuration.STOWAWAY_PEER_CONFIG_PATH}")
    tmpfile_location = "/tmp/peer1.conf"
    stream_copy_from_pod(stowaway_pod.items[0].metadata.name, configuration.NAMESPACE,
                         configuration.STOWAWAY_PEER_CONFIG_PATH,
                         tmpfile_location)

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
        core_v1_api.create_namespaced_secret(body=secret, namespace=configuration.NAMESPACE)
        logger.info(f"Cargo connection secret created")
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            # the connection secret deployment already exist
            logger.warning(f"Cargo connection secret exists, now patching it with current data")
            core_v1_api.patch_namespaced_secret(
                name=secret.metadata.name, body=secret,
                namespace=configuration.NAMESPACE
            )
            logger.info(f"Cargo connection secret patched")
        else:
            logger.exception(e)
            raise e
    except Exception as e:
        logger.exception(e)

