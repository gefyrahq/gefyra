from datetime import datetime

import kopf
import kubernetes as k8s

from gefyra.configuration import configuration
from gefyra.resources.configmaps import add_route


@kopf.on.create("interceptrequest")
async def interceptrequest_created(body, logger, **kwargs):
    from gefyra.stowaway import STOWAWAY_POD

    core_v1_api = k8s.client.CoreV1Api()

    # is this connection already established
    established = body.get("established")
    # destination host and port
    destinationIP = body.get("destinationIP")
    destinationPort = body.get("destinationPort")
    # the target Pod information
    targetPod = body.get("targetPod")
    targetContainer = body.get("targetContainer")
    targetContainerPort = body.get("targetContainerPort")

    configmap_update = add_route(destinationIP, destinationPort)
    logger.info(configmap_update)
    core_v1_api.replace_namespaced_config_map(
        name=configmap_update.metadata.name,
        body=configmap_update,
        namespace=configuration.NAMESPACE,
    )
    logger.info("Stowaway proxy route configmap patched")

    if STOWAWAY_POD:
        # notify the Stowaway Pod about the update
        logger.info(f"Notify {STOWAWAY_POD} about the new proxy route configmap")
        try:
            core_v1_api.patch_namespaced_pod(
                name=STOWAWAY_POD,
                body={
                    "metadata": {
                        "annotations": {"operator": f"updated-proxyroute-" f"{datetime.now().strftime('%Y%m%d%H%M%S')}"}
                    }
                },
                namespace=configuration.NAMESPACE,
            )
        except k8s.client.exceptions.ApiException as e:
            logger.exception(e)

    print(established)
    print(destinationIP)
    print(destinationPort)
    print(targetPod)
    print(targetContainer)
    print(targetContainerPort)
