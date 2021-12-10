import kopf
import kubernetes as k8s

from gefyra.configuration import configuration
from gefyra.resources.configmaps import add_route, remove_route
from gefyra.utils import notify_stowaway_pod

core_v1_api = k8s.client.CoreV1Api()


@kopf.on.create("interceptrequest")
async def interceptrequest_created(body, logger, **kwargs):
    from gefyra.stowaway import STOWAWAY_POD

    # is this connection already established
    # established = body.get("established")
    # destination host and port
    destination_ip = body.get("destinationIP")
    destination_port = body.get("destinationPort")
    # the target Pod information
    # target_pod = body.get("targetPod")
    # target_workload = body.get("targetWorkload")
    # target_container = body.get("targetContainer")
    # target_container_port = body.get("targetContainerPort")

    configmap_update = add_route(destination_ip, destination_port)
    core_v1_api.replace_namespaced_config_map(
        name=configmap_update.metadata.name,
        body=configmap_update,
        namespace=configuration.NAMESPACE,
    )
    logger.info("Added intercept route: Stowaway proxy route configmap patched")

    if STOWAWAY_POD:
        notify_stowaway_pod(STOWAWAY_POD, core_v1_api, configuration)
    else:
        logger.error("Could not notify Stowaway about the new intercept request")


@kopf.on.delete("interceptrequest")
async def interceptrequest_deleted(body, logger, **kwargs):
    from gefyra.stowaway import STOWAWAY_POD

    # is this connection already established
    # established = body.get("established")
    # destination host and port
    destination_ip = body.get("destinationIP")
    destination_port = body.get("destinationPort")
    # the target Pod information
    # target_pod = body.get("targetPod")
    # target_workload = body.get("targetWorkload")
    # target_container = body.get("targetContainer")
    # target_container_port = body.get("targetContainerPort")

    configmap_update = remove_route(destination_ip, destination_port)
    core_v1_api.replace_namespaced_config_map(
        name=configmap_update.metadata.name,
        body=configmap_update,
        namespace=configuration.NAMESPACE,
    )
    logger.info("Remove intercept route: Stowaway proxy route configmap patched")

    if STOWAWAY_POD:
        notify_stowaway_pod(STOWAWAY_POD, core_v1_api, configuration)
    else:
        logger.error("Could not notify Stowaway about the new intercept request")
